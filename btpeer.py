#!/usr/bin/python

# btpeer.py

import socket
import struct
import threading
import time
import traceback


def btdebug( msg ):
	print("[%s] %s" % ( str(threading.currentThread().getName()), msg ))


#==============================================================================
class BTPeer:

	def __init__( self, maxpeers, serverport, myid=None, serverhost = None ):
		self.debug = 1

		self.maxpeers = int(maxpeers)
		self.serverport = int(serverport)
		if serverhost: self.serverhost = serverhost
		else: self.__initserverhost()

		if myid: self.myid = myid
		else: self.myid = '%s:%d' % (self.serverhost, self.serverport)

		self.peerlock = threading.Lock()  # ensure proper access to
									# peers list (maybe better to use
									# threading.RLock (reentrant))
		self.peers = {}		# peerid ==> (host, port) mapping
		self.shutdown = False  # used to stop the main loop

		self.handlers = {}
		self.router = None


	def __initserverhost( self ):
		s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
		s.connect( ( "www.google.com", 80 ) )
		self.serverhost = s.getsockname()[0]
		s.close()


	def __debug( self, msg ):
		if self.debug:
			btdebug( msg )


	def __handlepeer( self, clientsock ):

		self.__debug( 'New child ' + str(threading.currentThread().getName()) )
		self.__debug( 'Connected ' + str(clientsock.getpeername()) )

		host, port = clientsock.getpeername()
		peerconn = BTPeerConnection( self.myid, host, port, clientsock, debug=False )

		try:
			msgtype, msgdata = peerconn.recvdata()
			print(str(type(msgtype)))
			msgtype = msgtype.decode('utf-8')
			if msgtype: msgtype = msgtype.upper()
			if msgtype not in self.handlers:
				self.__debug( 'Not handled: %s: %s' % (msgtype, msgdata) )
			else:
				self.__debug( 'Handling peer msg: %s: %s' % (msgtype, msgdata) )
				self.handlers[ msgtype ]( peerconn, msgdata )
				self.__debug("exiting handlers early")
		except KeyboardInterrupt:
			raise
			self.shutdown = True
		except:
			if self.debug:
				traceback.print_exc()
		
		self.__debug( 'Disconnecting ' + str(clientsock.getpeername()) )
		peerconn.close()

	# end handlepeer method


	def __runstabilizer( self, stabilizer, delay ):
		while not self.shutdown:
			stabilizer()
			time.sleep( delay )


	def setmyid( self, myid ):
		self.myid = myid


	def startstabilizer( self, stabilizer, delay ):
		t = threading.Thread( target = self.__runstabilizer, 
					  args = [ stabilizer, delay ] )
		t.start()

	
	def addhandler( self, msgtype, handler ):
		assert len(msgtype) == 4
		self.handlers[ msgtype ] = handler


	def addrouter( self, router ):
		self.router = router


	def addpeer( self, peerid, host, port ):
		if peerid not in self.peers and (self.maxpeers == 0 or len(self.peers) < self.maxpeers):
			self.peers[ peerid ] = (host, int(port))
			return True
		else:
			return False


	def getpeer( self, peerid ):
		assert peerid in self.peers	# maybe make this just a return NULL?
		return self.peers[ peerid ]


	def removepeer( self, peerid ):
		if peerid in self.peers:
			del self.peers[ peerid ]


	def addpeerat( self, loc, peerid, host, port ):
		self.peers[ loc ] = (peerid, host, int(port))


	def getpeerat( self, loc ):
		if loc not in self.peers:
			return None
		return self.peers[ loc ]


	def removepeerat( self, loc ):
		removepeer( self, loc ) 


	def getpeerids( self ):
		return self.peers.keys()


	def numberofpeers( self ):
		return len(self.peers)


	def maxpeersreached( self ):
		assert self.maxpeers == 0 or len(self.peers) <= self.maxpeers
		return self.maxpeers > 0 and len(self.peers) == self.maxpeers


	def makeserversocket( self, port, backlog=5 ):
		s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
		s.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
		s.bind( ( '', port ) )
		s.listen( backlog )
		return s


	def sendtopeer( self, peerid, msgtype, msgdata, waitreply=True ):
		if self.router:
			nextpid, host, port = self.router( peerid )
		if not self.router or not nextpid:
			self.__debug( 'Unable to route %s to %s' % (msgtype, peerid) )
			return None
		#host,port = self.peers[nextpid]
		return self.connectandsend( host, port, msgtype, msgdata, pid=nextpid, waitreply=waitreply )
	

	def connectandsend( self, host, port, msgtype, msgdata, 
			pid=None, waitreply=True ):
		msgreply = []
		try:
			peerconn = BTPeerConnection( pid, host, port, debug=self.debug )
			peerconn.senddata( msgtype, msgdata )
			self.__debug( 'Sent %s: %s' % (pid, msgtype) )
			
			if waitreply:
				onereply = peerconn.recvdata()
				while (onereply != (None,None)):
					msgreply.append( onereply )
					# self.__debug( 'Got reply %s: %s' % ( pid, str(msgreply) ) )
					onereply = peerconn.recvdata()
			peerconn.close()
		except KeyboardInterrupt:
			raise
		except:
			if self.debug:
				traceback.print_exc()
		
		return msgreply

	# end connectsend method


	def checklivepeers( self ):
		todelete = []
		for pid in self.peers:
			isconnected = False
			try:
				self.__debug( 'Check live %s' % pid )
				host,port = self.peers[pid]
				peerconn = BTPeerConnection( pid, host, port, debug=self.debug )
				peerconn.senddata( 'PING', '' )
				isconnected = True
			except:
				todelete.append( pid )
			if isconnected:
				peerconn.close()
		self.peerlock.acquire()
		try:
			for pid in todelete: 
				if pid in self.peers: del self.peers[pid]
		finally:
			self.peerlock.release()
	# end checklivepeers method


	def mainloop( self ):
		s = self.makeserversocket( self.serverport )
		s.settimeout(2)
		self.__debug( 'Server started: %s (%s:%d)'
				  % ( self.myid, self.serverhost, self.serverport ) )
		
		while not self.shutdown:
			try:
				self.__debug( 'Listening for connections...' )
				clientsock, clientaddr = s.accept()
				clientsock.settimeout(None)

				# self.__handlepeer(clientsock)
				t = threading.Thread( target = self.__handlepeer, args = [ clientsock ] )
				t.start()
			except KeyboardInterrupt:
				print('KeyboardInterrupt: stopping mainloop')
				self.shutdown = True
				continue
			except:
				if self.debug:
					# traceback.print_exc()
					continue

		# end while loop
		self.__debug( 'Main loop exiting' )

		s.close()

	# end mainloop method

# end BTPeer class




# **********************************************************




class BTPeerConnection:

	def __init__( self, peerid, host, port, sock=None, debug=True ):

		self.id = peerid
		print(str(self.id))
		self.debug = debug


		if not sock:
			self.s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
			self.s.connect( ( host, int(port) ) )
		else:
			self.s = sock

		self.sd = self.s.makefile( 'rwb', 0)


	def __makemsg( self, msgtype, msgdata ):
		self.__debug("start of makemsg")
		msglen = len(msgdata)
		if msgtype != "FILE":
			msgdata = msgdata.encode('utf-8')
		msgtype = msgtype.encode('utf-8')
		msg = struct.pack( "!4sL%ds" % msglen, msgtype, msglen, msgdata )
		#print("msg" + str(msg))
		self.__debug("end of makemsg")
		return msg


	def __debug( self, msg ):
		if self.debug:
			btdebug( msg )


	def senddata( self, msgtype, msgdata ):
		
		self.__debug("senddata function")
		try:
			msg = self.__makemsg( msgtype, msgdata )
			self.sd.write( msg )
			self.sd.flush()
		except KeyboardInterrupt:
			raise
		except:
			if self.debug:
				traceback.print_exc()
			traceback.print_exc()
			return False
		return True


	def recvdata( self ):
		try:
			msgtype = self.sd.read( 4 )
			if not msgtype: return (None, None)

			lenstr = self.sd.read( 4 )
			msglen = int(struct.unpack( "!L", lenstr )[0])
			msg = ""
			print("msg of type: " + str(msgtype))

			if msgtype == b'FILE':
				print("FILE!!!!")
				msg = b""
				while len(msg) != msglen:
					data = self.sd.read( min(2048, msglen - len(msg)) )
					if not len(data):
						break
					msg += data
				
			else:
				print("not a FILE!!!!")
				while len(msg) != msglen:
					data = self.sd.read( min(2048, msglen - len(msg)) )
					if not len(data):
						break
					msg += data.decode('utf-8')
			if len(msg) != msglen:
				return (None, None)

		except KeyboardInterrupt:
			raise
		except:
			if self.debug:
				traceback.print_exc()
			return (None, None)

		return ( msgtype, msg )

	# end recvdata method


	def close( self ):
		self.s.close()
		self.s = None
		self.sd = None


	def __str__( self ):
		return "|%s|" % peerid
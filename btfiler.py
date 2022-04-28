#!/usr/bin/python

from btpeer import *
import os

PEERNAME = "NAME"   # request a peer's canonical id
LISTPEERS = "LIST"
INSERTPEER = "JOIN"
QUERY = "QUER"
QRESPONSE = "RESP"
FILEGET = "FGET"
SENDFILE = "FILE"
PEERQUIT = "QUIT"
PEERPING = "PING"

REPLY = "REPL"
ERROR = "ERRO"


# Assumption in this program:
#   peer id's in this application are just "host:port" strings

#==============================================================================
class FilerPeer(BTPeer):
#==============================================================================
	def __init__(self, maxpeers, serverport):
		BTPeer.__init__(self, maxpeers, serverport)
		
		self.files = {}  # available files: name --> peerid mapping

		self.addrouter(self.__router)

		handlers = {LISTPEERS : self.__handle_listpeers,
				INSERTPEER : self.__handle_insertpeer,
				PEERNAME: self.__handle_peername,
				QUERY: self.__handle_query,
				QRESPONSE: self.__handle_qresponse,
				FILEGET: self.__handle_fileget,
				SENDFILE: self.__handle_fileget,
				PEERQUIT: self.__handle_quit,
				PEERPING: self.__handle_ping
			   }
		for mt in handlers:
			self.addhandler(mt, handlers[mt])

	# end FilerPeer constructor


	def __debug(self, msg):
		if self.debug:
			btdebug(msg)


	def __router(self, peerid):
		if peerid not in self.getpeerids():
			return (None, None, None)
		else:
			rt = [peerid]
			rt.extend(self.peers[peerid])
			return rt


	def __handle_insertpeer(self, peerconn, data):
		self.peerlock.acquire()
		try:
			try:
				peerid,host,port = data.split()

				if self.maxpeersreached():
					self.__debug('maxpeers %d reached: connection terminating' 
						  % self.maxpeers)
					peerconn.senddata(ERROR, 'Join: too many peers')
					return

				# peerid = '%s:%s' % (host,port)
				if peerid not in self.getpeerids() and peerid != self.myid:
					self.addpeer(peerid, host, port)
					self.__debug('added peer: %s' % peerid)
					peerconn.senddata(REPLY, 'Join: peer added: %s' % peerid)
				else:
					peerconn.senddata(ERROR, 'Join: peer already inserted %s' % peerid)
			except:
				self.__debug('invalid insert %s: %s' % (str(peerconn), data))
				peerconn.senddata(ERROR, 'Join: incorrect arguments')
		finally:
			self.peerlock.release()

	# end handle_insertpeer method


	def __handle_listpeers(self, peerconn, data):
		self.peerlock.acquire()
		try:
			self.__debug('Listing peers %d' % self.numberofpeers())
			peerconn.senddata(REPLY, '%d' % self.numberofpeers())
			for pid in self.getpeerids():
				host,port = self.getpeer(pid)
				peerconn.senddata(REPLY, '%s %s %d' % (pid, host, port))
		finally:
			self.peerlock.release()


	def __handle_peername(self, peerconn, data):
		peerconn.senddata(REPLY, self.myid)


	def __handle_query(self, peerconn, data):
	# self.peerlock.acquire()
		try:
			peerid, key, ttl = data.split()
			peerconn.senddata(REPLY, 'Query ACK: %s' % key)
		except:
			self.__debug('invalid query %s: %s' % (str(peerconn), data))
			peerconn.senddata(ERROR, 'Query: incorrect arguments')
		# self.peerlock.release()

		t = threading.Thread(target=self.__processquery, args=[peerid, key, int(ttl)])
		t.start()


	def __processquery(self, peerid, key, ttl):
		fpeerid = None
		self.__debug("Searching for %s" % (str(key)))
		print(self.files)
		for fname in self.files.keys():
			if key == fname:
				fpeerid = " ".join(str(x) for x in self.files[fname])
				if len(self.files[fname]) == 1:
					fpeerid += " " + str(self.myid)
				host,port = peerid.split(':')
			# print("fpeerid:" + str(fpeerid))
			# print("host:" + str(host))
			# print("port:" + str(port))
			# self.__debug("host = %s, port = %s" % (host, port))
			# can't use sendtopeer here because peerid is not necessarily
			# an immediate neighbor
		if fpeerid:
			self.connectandsend(host, int(port), QRESPONSE, '%s %s' % (fname, fpeerid), pid=peerid)
		return
		# will only reach here if key not found... in which case
		# propagate query to neighbors
		if ttl > 0:
			msgdata = '%s %s %d' % (peerid, key, ttl - 1)
			for nextpid in self.getpeerids():
				self.sendtopeer(nextpid, QUERY, msgdata)


	def __handle_qresponse(self, peerconn, data):
		try:
			self.__debug("qresp: data = %s" % str(data))
			# print(type(data))
			splitData = data.split()
			# print(splitData)
			fname = splitData[0]
			fsize = splitData[1]
			fpeerids = splitData[2:]
			# print(fname)
			# print(fsize)
			# print(fpeerids)
			self.__debug("%s" % str(self.files))
			if fname in self.files:
				for fpeerid in fpeerids:
					if fpeerid not in self.files[fname]:
						self.files[fname][1].append(fpeerid)
						self.__debug('%s' % (self.files[fname]))
					else:
						self.__debug('Can\'t add duplicate peer to file %s %s' % (fname, fpeerid))
			else:
				# print(self.id)
				# print("%s %s" % (peerconn.host, peerconn.port))
				self.files[fname] = [fsize, fpeerids]
			self.__debug('%s' % (self.files[fname]))
		except:
			#if self.debug:
			traceback.print_exc()


	def __handle_fileget(self, peerconn, data):
		fname, sIndex = data.split(",")
		sIndex = int(sIndex) * 1000000
		
		if fname not in self.files:
			self.__debug('File not found %s' % fname)
			peerconn.senddata(ERROR, 'File not found')
			return
		try:
			filepath = str(peerconn.id).split(":")[1] + "/" + fname
			fd = open(filepath, 'rb')
			fd.seek(sIndex)
			self.__debug("file size: %s" % str(os.path.getsize(filepath)))
			
			filedata = b""
			filedata = fd.read(1000000)
			
			fd.close()
		except:
			self.__debug('Error reading file %s' % fname)
			peerconn.senddata(ERROR, 'Error reading file')
			traceback.print_exc()
			return

		self.__debug("sending file!!!!")
		peerconn.senddata(SENDFILE, filedata)
		self.__debug("after sending file!!!!")


	def __handle_quit(self, peerconn, data):
		self.peerlock.acquire()
		try:
			peerid = data.lstrip().rstrip()
			if peerid in self.getpeerids():
				msg = 'Quit: peer removed: %s' % peerid 
				self.__debug(msg)
				peerconn.senddata(REPLY, msg)
				self.removepeer(peerid)
			else:
				msg = 'Quit: peer not found: %s' % peerid 
				self.__debug(msg)
				peerconn.senddata(ERROR, msg)
		finally:
			self.peerlock.release()


	def __handle_ping(self, peerconn, data):
		try:
			peerconn.senddata(REPLY, "Pong!")
		except:
			peerconn.senddata(ERROR, 'Error pinging')

	def buildpeers(self, host, port, hops=1):
		if self.maxpeersreached() or not hops or port == 0:
			return

		peerid = None

		self.__debug("Building peers from (%s,%s)" % (host,port))

		try:
			_, peerid = self.connectandsend(host, port, PEERNAME, '')[0]

			self.__debug("contacted " + peerid)
			resp = self.connectandsend(host, port, INSERTPEER, 
						'%s %s %d' % (self.myid, 
								  self.serverhost, 
								  self.serverport))[0]
			self.__debug(str(resp))
			if (resp[0] != REPLY) or (peerid in self.getpeerids()):
				return

			self.addpeer(peerid, host, port)

			# do recursive depth first search to add more peers
			resp = self.connectandsend(host, port, LISTPEERS, '', pid=peerid)
			if len(resp) > 1:
				resp.reverse()
				resp.pop()	# get rid of header count reply
				while len(resp):
					nextpid,host,port = resp.pop()[1].split()
					if nextpid != self.myid:
						self.buildpeers(host, port, hops - 1)
		except:
			if self.debug:
				traceback.print_exc()
			self.removepeer(peerid)


	def addlocalfile(self, filename):
		self.files[filename] = []
		self.files[filename].append(os.path.getsize(str(self.serverport) + "/" + filename))
		# print(self.files[filename][0])
		self.__debug("Added local file %s" % filename)

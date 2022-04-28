import filergui.py as *

def main():
	if len(sys.argv) < 4:
		print("Syntax: %s server-port max-peers peer-ip:port" % sys.argv[0])
		sys.exit(-1)

	serverport = int(sys.argv[1])
	maxpeers = sys.argv[2]
	peerid = sys.argv[3]
	app = BTGui( firstpeer=peerid, maxpeers=maxpeers, serverport=serverport )
	app.mainloop()

if __name__=='__main__':
	main()
# P2P-Implementation

This is a python 3.10 implementation of a P2P file sharing network which is a modified version of [PeerBase](https://github.com/nadeemabdulhamid/PeerBase). It utilizes the native python TCP sockets to transmit data and download files from multiple peers at once.

## Instructions to launch

'''
python filergui.py <server-port> <max-peers> <peer-ip:port>
'''

The <server-port> argument is the port which you want your client to be on. Your IP is automatically assumed to be the one you are on natively. The next argument, <max-peers>, allows the user to decide how many peers they would like to be connected to at one time. Finally, the last argument, <peer-ip:port>, is the client to which your are connecting. As soon as your client connects to this peer your client will request and add all of this peer's peers to your peer list.

For example:

'''
python filergui.py 9001 10 localhost:9000
'''
and
'''
python filergui.py 9002 10 localhost:9001
'''
and
'''
python filergui.py 9003 10 localhost:9001
'''

Launch the instances in the logical order, so the peer which you are connecting has already been launched.

This project was programmed by Charles Misback, clmisback on github.

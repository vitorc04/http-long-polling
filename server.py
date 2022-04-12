from twisted.internet.protocol import Protocol, Factory
from struct import pack, unpack
import collections
from time import time

def install_twisted_reactor():

    import sys

    if 'bsd' in sys.platform or sys.platform.startswith('darwin'):
         from twisted.internet import kqreactor
         kqreactor.install()
    elif sys.platform in ['win32']:
         from twisted.internet.iocpreactor import reactor as iocpreactor
         iocpreactor.install()
    elif sys.platform.startswith('linux'):
         from twisted.internet import epollreactor
         epollreactor.install()
    else:
         from twisted.internet import default as defaultreactor
         defaultreactor.install()

    from twisted.internet import reactor
    
    return reactor


class Stack(Protocol):

    def __init__(self, factory):
        self.factory = factory
        self.bytesremaining = None
        self.payload = ""
        self.headerseen = False
        self.isconnected = False

    def connectionMade(self):

	self.isconnected = True
	self.factory.numprotocol += 1
	now = time()
	if self.factory.numprotocol == 101:
	    if (int(time() - self.factory.
                            clientsmap[self.factory.clients[-1]]) > 10):
                self.factory.clients[-1].transport.loseConnection()
                self.factory.clientsmap[self] = now
                self.factory.clients.insert(0,self)
	    else:
                retval = pack('B',255)	
                self.transport.write(retval)
                self.factory.clientsmap[self] = now
                self.factory.clients.insert(0,self)
                self.transport.loseConnection()
            return
        self.factory.clientsmap[self] = now
        self.factory.clients.insert(0,self)

    def connectionLost(self, reason):

        self.isconnected = False
        self.factory.numprotocol -= 1
        self.factory.clients.remove(self)
        del self.factory.clientsmap[self]

    def dataReceived(self, data):
        if self.headerseen == False:
	    header = unpack('B', data[0])[0]
            if header == 128:
                if len(self.factory.stack) != 0:
                    self.pop()
                else:
                    self.factory.popstack.appendleft(self)
                self.headerseen = True
                return
            self.bytesremaining = unpack('B',data[0])[0]
            if len(data) > 1 :
                self.payload += data[1:]
                self.bytesremaining -= len(data) - 1
            self.headerseen = True
        else:
            self.payload += data
            self.bytesremaining -= len(data) 
        if self.bytesremaining == 0:
            if len(self.factory.stack) < 100:
                self.factory.stack.appendleft(self.payload)
                retval = pack('B',0)
                self.transport.write(retval)
                self.transport.loseConnection()
            else:
                self.factory.pushstack.appendleft(self)
            if len(self.factory.popstack) != 0:
                popstackval = self.factory.popstack.pop()
                if not popstackval.isconnected:
                    return
                popstackval.pop()
	
    def pop(self):
        stackval = self.factory.stack.popleft() 
        retval = pack('B',len(stackval))
        self.transport.write(retval)
        self.transport.write(stackval)
        self.transport.loseConnection()
        if len(self.factory.pushstack) != 0:
            pushstackval = self.factory.pushstack.pop()
            if not pushstackval.isconnected:
                return
            self.factory.stack.appendleft(pushstackval.payload)
            retval = pack('B',0)
            pushstackval.transport.write(retval)
            pushstackval.transport.loseConnection()

class StackFactory(Factory):

    def __init__(self):
        self.numprotocol = 0
        self.clients = []
        self.stack = collections.deque()
        self.popstack = collections.deque()
        self.pushstack = collections.deque()
        self.clientsmap = {}

    def buildProtocol(self, addr):
        return Stack(self)

if __name__ == '__main__':
    reactor = install_twisted_reactor()
    reactor.listenTCP(8080, StackFactory())
    reactor.run()
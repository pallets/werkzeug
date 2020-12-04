from .utils import ThreadedRequest

#: a thread local proxy request object
request = ThreadedRequest()
del ThreadedRequest

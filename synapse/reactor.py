from synapse.common import *

class Reactor:
    '''
    A class for registraction of one-to-one callbacks.
    ( much like a switch-case in C )
    Unlike an EventBus, only one action may be registered
    for a given mesg type and the function is expected to
    return a result.

    rtor = Reactor()

    def doFooBar(mesg):
        return 20 + mesg[1].get('x')

    rtor.act('foo:bar', doFooBar)

    y = rtor.react( tufo('foo:bar', x=30) )

    # y is now 50...

    '''
    def __init__(self):
        self.actfuncs = {}

    def act(self, name, func):
        '''
        Register a handler for an action by name.

        Example:

            rtor.act('foo:bar', doFooBar)

        '''
        self.actfuncs[name] = func

    def react(self, mesg):
        '''
        Dispatch to the handler and return his response.

        Example:

            resp = rtor.react(mesg)

        Notes:

            * Handler exceptions *will* propigate upward
        '''
        func = self.actfuncs.get(mesg[0])
        if func == None:
            raise NoSuchAct(mesg[0])

        return func(mesg)

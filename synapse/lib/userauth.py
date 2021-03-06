import hashlib
import fnmatch

import synapse.lib.cache as s_cache

from synapse.common import *
from synapse.eventbus import EventBus

class Rules:
    '''
    Glob based rules evaluator class (with caching).

    The Rules cache will use the UserAuth event bus to sync.
    '''
    def __init__(self, auth, user):

        self.user = user
        self.auth = auth

        self.auth.on('auth:bump:%s' % user, self._onBumpUser )

        # only triggered if auth is a proxy and reconnects
        self.auth.on('tele:sock:init', self._onTeleSock )

        self.cache = {}
        self.rules = auth.getUserRules(user)

    def _onTeleSock(self, mesg):
        self.rules = self.auth.getUserRules(user)
        self.cache.clear()

    def _onBumpUser(self, mesg):
        self.rules = mesg[1].get('rules')
        self.cache.clear()

    def allow(self, perm):
        '''
        Check if the current rules allow the given perm.

        Example:

            if rules.allow('foo.bar'):
                dostuff()

        '''
        ret = self.cache.get(perm)

        if ret == None:
            ret = False
            for rule in self.rules:
                if fnmatch.fnmatch(perm,rule):
                    ret = True
                    break

            self.cache[perm] = ret

        return ret

class UserAuth(EventBus):
    '''
    Store users, roles, and rules for AAA in a cortex.
    '''
    def __init__(self, core):
        EventBus.__init__(self)

        self.core = core
        self.model = core.genDataModel()

        self.model.addTufoForm('auth:user')
        self.model.addTufoProp('auth:user','apikey', defval='')
        self.model.addTufoProp('auth:user','shadow:sha256', defval='')

        self.model.addTufoForm('auth:role')

        self.model.addTufoForm('auth:userrole')
        self.model.addTufoProp('auth:userrole','user')
        self.model.addTufoProp('auth:userrole','role')

        self.users = s_cache.TufoPropCache(core,'auth:user')
        self.roles = s_cache.TufoPropCache(core,'auth:role')

        self.rules = s_cache.KeyCache(self._getUserRulesCache)

    def addUser(self, user, **props):
        '''
        Add a user to the UserAuth cortex.
        '''
        if self.users.get(user) != None:
            raise DupUser(user)

        usfo = self.core.formTufoByProp('auth:user', user, **props)
        self.users.put(user,usfo)

        return usfo

    def getUser(self, user):
        '''
        Return a user tufo or None by name.

        Example:

            user = auth.getUser('visi')
            if role != None:
                dostuff(role)
        '''
        return self.users.get(user)

    def getRole(self, role):
        '''
        Return a role tufo or None by name.

        Example:

            role = auth.getRole('admin')
            if role != None:
                dostuff(role)

        '''

    def addUserRule(self, user, rule):
        '''
        Add a rule glob for a user.
        '''
        usfo = self._reqUserTufo(user)
        self.core.addTufoList(usfo, 'auth:rules', rule)
        self._bumpUserRules(user)

    def getUserRoles(self, user):
        '''
        Return a list of the roles for the given user.
        '''
        usfo = self._reqUserTufo(user)
        userroles = self.core.getTufosByProp('auth:userrole:user',user)
        return [ u[1].get('auth:userrole:role') for u in userroles ]

    def addUserRole(self, user, role):
        '''
        Grant a role to a user.
        '''
        usfo = self._reqUserTufo(user)
        rofo = self._reqRoleTufo(role)

        props = {'user':user,'role':role}
        self.core.formTufoByProp('auth:userrole', '%s:%s' % (user,role), **props)

        self._bumpUserRules(user)

    def _bumpUserRules(self, user):
        rules = self.getUserRules(user)
        self.fire('auth:bump:%s' % user, rules=rules)

    def delUserRole(self, user, role):
        '''
        Revoke a role from a user.
        '''
        usfo = self._reqUserTufo(user)
        rofo = self._reqRoleTufo(role)

        self.core.delTufoByProp('auth:userrole', '%s:%s' % (user,role))

        self._bumpUserRules(user)

    def addRoleRule(self, role, rule):
        '''
        Add a rule glob for the given role.
        '''
        rofo = self._reqRoleTufo(role)
        self.core.addTufoList(rofo,'auth:rules',rule)

        for userrole in self.core.getTufosByProp('auth:userrole:role',role):
            user = userrole[1].get('auth:userrole:user')
            self._bumpUserRules(user)

    def delRoleRule(self, role, rule):
        '''
        Delete a rule for the given role.
        '''
        rofo = self._reqRoleTufo(role)
        self.core.delTufoListValu(rofo,'auth:rules',rule)

        for userrole in self.core.getTufosByProp('auth:userrole:role',role):
            user = userrole[1].get('auth:userrole:user')
            self._bumpUserRules(user)

    def delUserRule(self, user, rule):
        '''
        Delete a rule for the given user.
        '''
        usfo = self._reqUserTufo(user)
        self.core.delTufoListValu(usfo,'auth:rules',rule)
        self._bumpUserRules(user)

    def addRole(self, role, **props):
        '''
        Add a new role to the UserAuth cortex.
        '''
        if self.roles.get(role) != None:
            raise DupRole(role)

        rofo = self.core.formTufoByProp('auth:role', role, **props)
        self.roles.put(role,rofo)
        return rofo

    def delUser(self, user):
        '''
        Delete a user ( and associated userroles ) by name.

        Example:

            auth.delUser('visi')

        '''
        usfo = self._reqUserTufo(user)
        self.core.delTufoByProp('auth:user', user)
        self.core.delTufosByProp('auth:userrole:user',user)

        self.users.pop(user)
        self.rules.pop(user)

    def delRole(self, role):
        '''
        Delete a role ( and associated userroles ) by name.

        Example:

            auth.delRole('root')

        '''
        rofo = self._reqRoleTufo(role)
        userroles = self.core.getTufosByProp('auth:userrole:role', role)

        users = [ u[1].get('auth:userrole:user') for u in userroles ]

        self.core.delTufosByProp('auth:role', role)
        self.core.delTufosByProp('auth:userrole:role', role)

        self.roles.pop(role)
        [ self._bumpUserRules(user) for user in users ]

    def getUserRules(self, user):
        usfo = self._reqUserTufo(user)
        rules = self.core.getTufoList(usfo,'auth:rules')

        for userrole in self.core.getTufosByProp('auth:userrole:user', user):
            rofo = self.roles.get( userrole[1].get('auth:userrole:role') )
            rules.extend( self.core.getTufoList(rofo,'auth:rules') )

        return rules

    def _getUserRulesCache(self, user):
        return Rules(self, user)

    def isUserAllowed(self, user, perm):
        '''
        Returns True if a users rules ( or their roles rules ) allow a perm.
        '''
        rules = self.rules.get(user)
        return rules.allow(perm)

    def setUserProp(self, user, prop, valu):
        usfo = self._reqUserTufo(user)
        self.core.setTufoProp(usfo, prop, valu)

    def setRoleProp(self, role, prop, valu):
        rofo = self._reqRoleTufo(role)
        self.core.setTufoProp(rofo, prop, valu)

    def _reqUserTufo(self, user):
        usfo = self.users.get(user)
        if usfo == None:
            raise NoSuchUser(user)
        return usfo

    def _reqRoleTufo(self, role):
        rofo = self.roles.get(role)
        if rofo == None:
            raise NoSuchRole(role)
        return rofo


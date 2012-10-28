# -*- coding: utf-8 -*-

import os
import sys
import ldap
import crypt
import random
import string
import getpass
from yunohost import YunoHostError, win_msg, colorize, validate, get_required_args

def user_list(args, connections):
    """
    List YunoHost users from LDAP

    Keyword argument:
        args -- Dictionnary of values (can be empty)
        connections -- LDAP connection

    Returns:
        Dict
    """
    yldap = connections['ldap']
    user_attrs = ['uid', 'mail', 'cn']
    attrs = []
    result_dict = {}
    if args['offset']: offset = int(args['offset'])
    else: offset = 0
    if args['limit']: limit = int(args['limit'])
    else: limit = 1000
    if args['filter']: filter = args['filter']
    else: filter = 'uid=*'
    if args['fields']:
        for attr in args['fields']:
            if attr in user_attrs:
                attrs.append(attr)
                continue
            else:
                raise YunoHostError(22, _("Invalid field : ") + attr)        
    else:
        attrs = user_attrs

    result = yldap.search('ou=users,dc=yunohost,dc=org', filter, attrs)
    
    if len(result) > (0 + offset) and limit > 0:
        i = 0 + offset
        for entry in result[i:]:
           if i < limit:
               result_dict[str(i)] = entry 
               i += 1
    else:
        result_dict = { 'Notice' : _("No user found") }

    return result_dict


def user_create(args, connections):
    """
    Add user to LDAP

    Keyword argument:
        args -- Dictionnary of values (can be empty)

    Returns:
        Dict
    """
    yldap = connections['ldap']
    args = get_required_args(args, {
        'username': _('Username'), 
        'mail': _('Mail address'), 
        'firstname': _('Firstname'), 
        'lastname': _('Lastname'), 
        'password': _('Password')
    }, True)

    # Validate password length
    if len(args['password']) < 4:
        raise YunoHostError(22, _("Password is too short"))

    # Validate other values TODO: validate all values
    validate({
        args['username']    : r'^[a-z0-9_]+$', 
        args['mail']        : r'^[\w.-]+@[\w.-]+\.[a-zA-Z]{2,6}$',
    })

    yldap.validate_uniqueness({
        'uid'       : args['username'],
        'mail'      : args['mail'],
        'mailalias' : args['mail']
    })

    # Check if unix user already exists (doesn't work)
    #if not os.system("getent passwd " + args['username']):
    #    raise YunoHostError(17, _("Username not available"))

    #TODO: check if mail belongs to a domain

    # Get random UID/GID
    uid_check = gid_check = 0
    while uid_check == 0 and gid_check == 0:
        uid = str(random.randint(200, 99999))
        uid_check = os.system("getent passwd " + uid)
        gid_check = os.system("getent group " + uid)

    # Adapt values for LDAP
    fullname = args['firstname'] + ' ' + args['lastname']
    rdn = 'uid=' + args['username'] + ',ou=users'
    char_set = string.ascii_uppercase + string.digits
    salt = ''.join(random.sample(char_set,8))
    salt = '$1$' + salt + '$'
    pwd = '{CRYPT}' + crypt.crypt(str(args['password']), salt)
    attr_dict = {
        'objectClass'   : ['mailAccount', 'inetOrgPerson', 'posixAccount'],
        'givenName'     : args['firstname'],
        'sn'            : args['lastname'],
        'displayName'   : fullname,
        'cn'            : fullname,
        'uid'           : args['username'],
        'mail'          : args['mail'],
        'userPassword'  : pwd,
        'gidNumber'     : uid,
        'uidNumber'     : uid,
        'homeDirectory' : '/home/' + args['username'],
        'loginShell'    : '/bin/false'
    }

    if yldap.add(rdn, attr_dict):
        # Create user /home directory by switching user
        os.system("su - " + args['username'] + " -c ''")
        #TODO: Send a welcome mail to user
        win_msg(_("User successfully created"))
        return { _("Fullname") : fullname, _("Username") : args['username'], _("Mail") : args['mail'] }
    else:
        raise YunoHostError(169, _("An error occured during user creation"))

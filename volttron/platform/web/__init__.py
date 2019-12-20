# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from http.cookies import SimpleCookie
import logging
from urllib.parse import urlparse

from volttron.platform.certs import Certs, CertWrapper
from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.agent.utils import get_fq_identity
from volttron.platform import get_platform_config

try:
    import jwt
except ImportError:
    logging.getLogger().warning("Missing library jwt within web package.")

from . discovery import DiscoveryInfo, DiscoveryError

# Used outside so we make it available through this file.
from . master_web_service import MasterWebService

_log = logging.getLogger(__name__)


class NotAuthorized(Exception):
    pass


def get_bearer(env):

    # Test if HTTP_AUTHORIZATION header is passed
    http_auth = env.get('HTTP_AUTHORIZATION')
    if http_auth:
        auth_type, bearer = http_auth.split(' ')
        if auth_type.upper() != 'BEARER':
            raise NotAuthorized("Invalid HTTP_AUTHORIZATION header passed, must be Bearer")
    else:
        cookiestr = env.get('HTTP_COOKIE')
        if not cookiestr:
            raise NotAuthorized()
        cookie = SimpleCookie(cookiestr)
        bearer = cookie.get('Bearer').value.decode('utf-8')
    return bearer


def get_user_claims(env):
    algorithm, encode_key = __get_key_and_algorithm__(env)
    bearer = get_bearer(env)
    return jwt.decode(bearer, encode_key, algorithm=algorithm)


def __get_key_and_algorithm__(env):
    config = get_platform_config()
    publickey = env.get("WEB_PUBLIC_KEY")
    algorithm = 'RS256' if publickey is not None else 'HS256'
    if algorithm == 'HS256':
        if config.get('web-secret-key') is None:
            raise ValueError("invalid configuration detected web_secret_key must be set!")
    encode_key = publickey if algorithm == 'RS256' else config.get('web-secret-key')
    return algorithm, encode_key


def get_user_claim_from_bearer(bearer, web_secret_key=None, tls_public_key=None):
    if web_secret_key is None and tls_public_key is None:
        raise ValueError("web_secret_key or tls_public_key must be set")
    if web_secret_key is None and tls_public_key is None:
        raise ValueError("web_secret_key or tls_public_key must be set not both")

    if web_secret_key is not None:
        algorithm = 'HS256'
        pubkey = web_secret_key
    else:
        algorithm = 'RS256'
        pubkey = tls_public_key
        # if isinstance(tls_public_key, str):
        #     pubkey = CertWrapper.load_cert(tls_public_key)
    return jwt.decode(bearer, pubkey, algorithms=algorithm)


def build_vip_address_string(vip_root, serverkey, publickey, secretkey):
    """ Build a full vip address string based upon the passed arguments

    All arguments are required to be non-None in order for the string to be
    created successfully.

    :raises ValueError if one of the parameters is None.
    """
    _log.debug("root: {}, serverkey: {}, publickey: {}, secretkey: {}".format(
        vip_root, serverkey, publickey, secretkey))
    parsed = urlparse(vip_root)
    if parsed.scheme == 'tcp':
        if not (serverkey and publickey and secretkey and vip_root):
            raise ValueError("All parameters must be entered.")

        root = "{}?serverkey={}&publickey={}&secretkey={}".format(
            vip_root, serverkey, publickey, secretkey)

    elif parsed.scheme == 'ipc':
        root = vip_root
    else:
        raise ValueError('Invalid vip root specified!')

    return root

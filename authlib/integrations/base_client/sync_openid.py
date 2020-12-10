from authlib.jose import JsonWebToken, JsonWebKey
from authlib.oidc.core import UserInfo, CodeIDToken, ImplicitIDToken


class OpenIDMixin(object):
    def fetch_jwk_set(self, force=False):
        raise NotImplementedError()

    def userinfo(self, **kwargs):
        """Fetch user info from ``userinfo_endpoint``."""
        metadata = self.load_server_metadata()
        resp = self.get(metadata['userinfo_endpoint'], **kwargs)
        data = resp.json()
        return UserInfo(data)

    def parse_id_token(self, token, nonce, claims_options=None, leeway=120):
        """Return an instance of UserInfo from token's ``id_token``."""
        if 'id_token' not in token:
            return None

        def load_key(header, _):
            jwk_set = JsonWebKey.import_key_set(self.fetch_jwk_set())
            try:
                return jwk_set.find_by_kid(header.get('kid'))
            except ValueError:
                # re-try with new jwk set
                jwk_set = JsonWebKey.import_key_set(self.fetch_jwk_set(force=True))
                return jwk_set.find_by_kid(header.get('kid'))

        claims_params = dict(
            nonce=nonce,
            client_id=self.client_id,
        )
        if 'access_token' in token:
            claims_params['access_token'] = token['access_token']
            claims_cls = CodeIDToken
        else:
            claims_cls = ImplicitIDToken

        metadata = self.load_server_metadata()
        if claims_options is None and 'issuer' in metadata:
            claims_options = {'iss': {'values': [metadata['issuer']]}}

        alg_values = metadata.get('id_token_signing_alg_values_supported')
        if not alg_values:
            alg_values = ['RS256']

        jwt = JsonWebToken(alg_values)
        claims = jwt.decode(
            token['id_token'], key=load_key,
            claims_cls=claims_cls,
            claims_options=claims_options,
            claims_params=claims_params,
        )
        # https://github.com/lepture/authlib/issues/259
        if claims.get('nonce_supported') is False:
            claims.params['nonce'] = None
        claims.validate(leeway=leeway)
        return UserInfo(claims)
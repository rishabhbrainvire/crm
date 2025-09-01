# You'll need to install PyJWT via pip 'pip install PyJWT' or your project packages file

import jwt
import time

METABASE_SITE_URL = "http://localhost:3001"
METABASE_SECRET_KEY = "1a85bf1e02973c7f6f0fc6ef2afa6f4248d21a9a40099fac9ed1b301852098dd"

payload = {
  "resource": {"dashboard": 2},
  "params": {
    
  },
  "exp": round(time.time()) + (60 * 10) # 10 minute expiration
}
token = jwt.encode(payload, METABASE_SECRET_KEY, algorithm="HS256")

iframeUrl = METABASE_SITE_URL + "/embed/dashboard/" + token + "#bordered=true&titled=true"
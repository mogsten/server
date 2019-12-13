import jwt
headers = {
   'kid': settings.SOCIAL_AUTH_APPLE_KEY_ID
}
payload = {
   'iss': settings.SOCIAL_AUTH_APPLE_TEAM_ID,
   'iat': timezone.now(),
   'exp': timezone.now() + timedelta(days=180),
   'aud': 'https://appleid.apple.com',
   'sub': settings.CLIENT_ID,
}
client_secret = jwt.encode(
   payload, 
   settings.SOCIAL_AUTH_APPLE_PRIVATE_KEY, 
   algorithm='ES256', 
   headers=headers
).decode("utf-8")

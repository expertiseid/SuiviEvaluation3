# En-têtes de sécurité des pages du site vitrine (inclus dans nginx.conf.template). Tout vient du site
# lui-même : scripts, polices, images, vidéos et API sont à la même adresse.
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
# Fonctions du navigateur : seul le plein écran (vidéos) sert au site.
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), fullscreen=(self), payment=(), usb=(), accelerometer=(), gyroscope=(), magnetometer=()" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;

# En-têtes de sécurité de l'application (inclus dans nginx.conf.template). Seules sources extérieures :
# les fonds de carte (OpenStreetMap, satellite Esri). Les réponses de l'API ont leurs propres en-têtes
# (apps.core.securite) : ne pas inclure ce fichier dans « location /api/ ».
# Rappel Nginx : un « add_header » dans un bloc location annule ceux du niveau au-dessus, d'où
# l'inclusion dans chaque bloc location concerné.
#
# Jeton (nonce) de la politique de contenu : tiré au hasard à chaque requête ($request_id), écrit dans
# la page à la place de JETON_CSP (balises de Vite et <meta property="csp-nonce">, lu par Mantine) et
# dans l'en-tête. Seuls les scripts et styles portant ce jeton sont acceptés (frontend/vite.config.ts).
sub_filter 'JETON_CSP' $request_id;
sub_filter_once off;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'nonce-$request_id'; style-src 'self' 'nonce-$request_id'; img-src 'self' data: blob: https://a.tile.openstreetmap.org https://b.tile.openstreetmap.org https://c.tile.openstreetmap.org https://server.arcgisonline.com; font-src 'self' data:; connect-src 'self' https://a.tile.openstreetmap.org https://b.tile.openstreetmap.org https://c.tile.openstreetmap.org https://server.arcgisonline.com; frame-src 'self' blob:; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

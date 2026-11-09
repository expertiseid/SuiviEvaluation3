# Commun aux deux serveurs de nginx.conf.template.
client_max_body_size 100m;
# Ne pas annoncer la version de Nginx dans les réponses.
server_tokens off;
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;

location ~ ^/(api|admin)/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_read_timeout 300;
}

location /static/ {
    alias /static/;
    expires 30d;
    add_header X-Content-Type-Options "nosniff" always;
}

# Fichiers assemblés de l'application : leur nom change à chaque version, on les garde longtemps.
location /assets/ {
    root /usr/share/nginx/html;
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header X-Content-Type-Options "nosniff" always;
    try_files $uri =404;
}

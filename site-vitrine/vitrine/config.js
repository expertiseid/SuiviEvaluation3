/*
 * Réglages du site vitrine. Le site est servi à l'adresse principale de la plateforme
 * (deploiement/nginx.conf) : l'API est alors à la même adresse (« /api/v1 »).
 * Aperçu sur un poste de développement (http://site.localhost:5310) : l'API locale.
 */
(function () {
  // Poste de développement : localhost, ou l'adresse du poste sur le réseau local (192.168.x.x, 10.x.x.x…).
  var hote = window.location.hostname;
  var local = /(^|\.)localhost$/.test(hote) || /^(192\.168|10|172\.(1[6-9]|2\d|3[01]))\./.test(hote);
  window.SITE = local
    ? {
        API: "http://" + hote + ":8093/api/v1",
        CONNEXION: "http://" + hote + ":5192/login",
        DEMO: "http://" + hote + ":5192/accueil?demo=1",
        VIDEOS: "http://" + hote + ":5192/videos",
      }
    : {
        API: "/api/v1",
        CONNEXION: "/login",
        DEMO: "/accueil?demo=1",
        VIDEOS: "/videos",
      };
})();

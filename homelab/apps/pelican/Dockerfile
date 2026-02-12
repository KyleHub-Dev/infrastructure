FROM ghcr.io/pelican-dev/panel:latest
COPY --from=docker.io/library/composer:latest /usr/bin/composer /usr/local/bin/composer

# Fix ownership for composer-writable files so plugin installation works
# under rootless podman (overlay copy-up requires owner write, not just group)
USER root
RUN chown www-data:www-data /var/www/html/composer.json /var/www/html/composer.lock /var/www/html/vendor
USER www-data

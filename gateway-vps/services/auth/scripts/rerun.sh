docker compose down -v
sudo rm -rf ./data/postgres
rm -f login-client.pat
git pull
docker compose up -d
sleep 10
docker compose ps
docker compose logs traefik --tail 50
docker compose logs db --tail 50
docker compose logs zitadel --tail 50
docker compose logs login --tail 50

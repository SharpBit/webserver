docker build -t sharpbitdev .
docker run -d --name sharpbitdev -p 127.0.0.1:4000:4000 sharpbitdev
docker start sharpbitdev
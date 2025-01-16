# Happy Robot Challenge

Steps to run docker Image: 
docker buildx build --platform linux/amd64 -t happyRobotImage .

aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin 442284680242.dkr.ecr.us-west-1.amazonaws.com

docker tag myimage:latest 442284680242.dkr.ecr.us-west-1.amazonaws.com/happyrobot/rest_api:latest

docker push 442284680242.dkr.ecr.us-west-1.amazonaws.com/happyrobot/rest_api:latest  

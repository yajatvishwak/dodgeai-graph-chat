FROM node:22-slim

WORKDIR /app

COPY web/frontend/package.json /app/
RUN npm install

COPY web/frontend/ /app/

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help up p1 p2 p3 down stop restart build logs ps pull-model clean fclean re

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start core services only (qdrant, indexer, conv-model)
	$(COMPOSE) up -d

p1: ## Start profile p1 (dashboard + core services)
	$(COMPOSE) --profile p1 up -d --build

p2: ## Start profile p2 (dashboard + api + core services)
	$(COMPOSE) --profile p2 up -d --build

p3: ## Start profile p3 (dashboard + api + core services)
	$(COMPOSE) --profile p3 up -d --build

build: ## Build all images (all profiles)
	$(COMPOSE) --profile p1 --profile p2 --profile p3 build

down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) --profile p1 --profile p2 --profile p3 down

stop: ## Stop containers without removing them
	$(COMPOSE) --profile p1 --profile p2 --profile p3 stop

restart: down up ## Restart core services

logs: ## Follow logs (usage: make logs s=qdrant)
	$(COMPOSE) --profile p1 --profile p2 --profile p3 logs -f $(s)

ps: ## List containers
	$(COMPOSE) --profile p1 --profile p2 --profile p3 ps

clean: down ## Remove containers and volumes (wipes qdrant + ollama data)
	$(COMPOSE) --profile p1 --profile p2 --profile p3 down -v

fclean: clean ## Also remove built images
	$(COMPOSE) --profile p1 --profile p2 --profile p3 down -v --rmi local

re: fclean p1 ## Full rebuild, then start p1
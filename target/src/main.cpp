#include "Tamagotchi.h"

Tamagotchi pet;

int main( void ) {
	while (42) {
		std::string action;
		std::cout << "=^._.^= ";
		std::getline(std::cin, action);
		pet.interact(action);
	}
}

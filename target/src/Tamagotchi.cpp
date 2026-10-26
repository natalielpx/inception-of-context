#include "Tamagotchi.h"

Tamagotchi::Tamagotchi( void ) : _asleep(false) {}

void Tamagotchi::interact( const std::string & action ) {
	if 		(action == "feed") 	feed();
	else if (action == "play") 	play();
	else if (action == "sleep") sleep();
	else 						wait();
}

void Tamagotchi::wake( void ) {
	_asleep = false;
	std::cout << "*yawns*" << std::endl;
	std::cout << "*wakes up*" << std::endl;
}

void Tamagotchi::feed( void ) {
	if (_asleep) wake();
	std::cout << "*eats*" << std::endl;
	std::cout << "miammmmm" << std::endl;
}

void Tamagotchi::play( void ) {
	if (_asleep) wake();
	std::cout << "*rolls ball around*" << std::endl;
}

void Tamagotchi::sleep( void ) {
	_asleep = true;
	std::cout << "zzzzZZ..." << std::endl;
}

// Tamagotchi does nothing
void Tamagotchi::wait( void ) {
	if (_asleep) return;
	std::cout << "..." << std::endl;
}
#ifndef TAMAGOTCHI_H
#define TAMAGOTCHI_H

#include <iostream>
#include <string>

class Tamagotchi {

public:
    Tamagotchi();

    // Player actions.
    void interact( const std::string & );
    void feed( void );
    void play( void );
    void sleep( void );
    void wake( void );
    void wait( void );

private:
    bool _asleep;

};

#endif
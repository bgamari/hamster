let nixpkgs = import <nixpkgs> {};
in with nixpkgs; callPackage ./hamster.nix { pythonPackages = python3Packages; }

A simple replacement for handheld sync
======================================

This is a replacement for handheld sync which I couldn't get to work reliably. It is intended for use as a script to be triggered on insertion of the device into the host machine via a udev rule. It makes a number of assumptions because I wrote this script for me

* appropriate udev rules have been configured to ensure the device has a deterministic path
* there is 1 playlist to sync to the device
* the prerequisites (python, flac2all, xmlstarlet) are installed and available
* all required paths are writeable
* the source is flac, the target is mp3
* wakeonlan is either installed or the jriver server is up already

Usage
-----

TODO
----

* manage the size of the conversion cache
* support different

Overrides
---------

if you want to use a different converter then override the "populate_conversion_cache" function

udev config
===========

device paths
------------

I use debian which provides https://wiki.debian.org/udev

An example of a rule to identify a particular SD card that lives in my car

    $ cat /etc/udev/rules.d/z21_persistent-local.rules
    ATTRS{manufacturer}=="SanDisk", ATTRS{product}=="Cruzer Fit", ATTRS{serial}=="4C530010460628103015", SYMLINK+="usbsdcardcar"

execute on insert
-----------------
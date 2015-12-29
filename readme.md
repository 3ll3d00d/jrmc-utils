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

* Install the prerequisites (JRMC, python, flac2all, xmlstarlet)
* Create a file containing the following properties, use your own paths
    
    JRMC_UTILS_DIR=/home/matt/github/jrmc-utils
    MEDIA_SRC_DIR=/media/music
    FLAC2ALL_DIR=/opt/flac2all/stable
    
    MEDIA_CACHE_DIR=/home/matt/test/cache
    JRMC_PLAYLIST_PATH="Devices\Alice\Sandisk Clip Sport - Main - Audiobook"
    HANDHELD_MOUNT=/mount/handheld/car
    HANDHELD_TARGET_DIR=/
    
* Create a creds file ~/.jrmc-utils containing entries for
    
    JRMC_HOST=
    JRMC_PORT=
    JRMC_USER=
    JRMC_PASS=
    JRMC_MAC=
    
* Call sync.sh passing the file name referenced in step 2
    
    sync.sh /path/to/mysync.conf
    

TODO
----

* manage the size of the conversion cache
* support different encoders
* handle jriver without authentication

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

Add an stanza like

    RUN+="/path/to/sync.sh sd_car.conf"

where that script is an example like that shown in usage
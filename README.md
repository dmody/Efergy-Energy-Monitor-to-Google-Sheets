This initial commit is a little half baked at this point, but I think the underlying concept and code will be useful for others attempting the same.   

The Pain Point:
The reason for this project is that Efergy, an producer of home energy monitors has ceased to exist and I'm left with a decent energy monitor but no way to archive the data, since their cloud service has disappeared.   I wanted a remotely accessible power dashboard I could access.   In so doing I discovered a few other things that make this current system possibly more informative and useful.  

The heart of the system is an Efergy Power Sensor that is IR based and sits on the outside of my house counting pulses from my meter.   The system is battery powered and sends a 433Mhz signal to a display unit and a what was a hub to get the data on the internet.   Others have proven they could listen to the 433 Mhz signal and have decoded the radio packets, so this is reusing that capabilty.  RTL_433 does a fine job of this.   

A raspberry Pi Zero 2 W has an SDR (software defined radio) dongle (a cheap one) plugged into it.  The pi runs headless.   Python Code is run as a service on the Pi to send the received radio information to google sheets.   In my case the Efergy unit transmitts every 30 seconds a number of pulses (i.e. 6) that when multiplied by the conversion factor of 1000 provides the number of watts used over that period of time  (see code for exact conversion equation).    This data is then transmitted to google sheets script which adds date/time and puts it into a spreadsheet.  Note that there is no control over when those 6 seconds occur, which makes integration of the power to calculate energy on an hour by hour basis somewhat more complicated sinced those 30 windows will cross over an hour.  ZOH algorimthm handles that integration without loosing or gaining energy.     

The google sheets contains a dashboard with power, time, signal strength (a proxy for battery conditions), SNR (not useful?).   Another sheet holds 1 day of data integrated over 5 minutes, another sheet holds hourly max/min/avg and total data, and another sheet holds daily max/min/avg and total energy data along with RSSI strength (a slow declining number is expected as battery levels drop).  

As the project moved along, I found out I have KASA smart plugs that monitor power and they can be brought into the system using the pi.  So those units provide handy ways to break down where the power is being used in the house.  The "name" assigned to them in the Kasa software is archived so you know where that breakdown is coming from and you can move the plug around to various devices, as you wish.  

In addtion, a Tempest station happens to be on the same network and the packets can be brought into the Pi to provide weather correlation.   Indoor conditions are also imported at the google sheets level.   

Some hints:  The Kasa units library requires it's own environment to run in.  That python code runs as it's own service.    The Efergy unit has it's own service, and that service is also sending the weather data.  So there are two independent programs sending data to the google sheets, which adds a bit of complexity and you may not need that.  

The Efergy unit was tricky to get working with RTL_433.  The frequency mine was operating at was 433.572 MHz.  A little off that and you don't get any data.   Also it uses the FSK transmissions instead of the more popular OOK method.  So, what worked for me was to set a range in the frequencies to listen to.  That's been very reliable.  Here is the command line to listen to the unit.  "rtl_433 -f 433.50M:433.58M -g 35 -F json -M time -M level "   You can change -g 35 to g -15 for less gain and still get a good signal.  

Both Python sheets use environment variables for passwords and google sheets script ID's, or you can just hardwire your information into the python code.     The KASA units also require your Kasa username and password to retrieve data from them.   

In the end it took me s 4 or 5 days of work and maybe something here will save you a bit of time, but no doubt you'll want to taylor it to your own needs.  

I know have what I consider to be a fairly handy little dashboard and data historian, and I have some thoughts on how to extend this into not just a monitor that you set and forget about.... stay tuned.  

The ..."Demo V1" files for the Raspberry Pi and Google sheets are a minimimum to get you going and you can see how easy this is to get working.  Well, easy once you have a million libraries installed on the PI, but otherwise easy.  

Cheers,
Dave

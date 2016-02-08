# CEEproject/ CM HA Demo
#### Below are the list of important files and their usages. Files are listed according to their position in the directoriy relative to the root path. 

| Source file                     | Usage/Description                                                                               |
|---------------------------------|-------------------------------------------------------------------------------------------------|
| GUIserver.py                    | ./GUIserver.py                                                                           |
|                                 | the most basic usage, will run the GUI Server on the local host with the address provided in the|
|                                 | config.json file.                                                                               |
|                                 | ./GUIserver.py debug                                                                            |
|                                 | This will run the GUI server in debug mode. *Most* debug messages will be displayed. I.e. The   |
|                                 | contaning the map of all VMs with their corresponding nodes, their call numbers. Alongside some |
|                                 | other additional log data such as the parsed lines and fragments found from the parsed lines in |
|                                 | the CM HA main.log file.                                                                        |
|                                 | ./GUIserver debug -v                                                                            |
|                                 | Extra verbose debug mode. In this mode, the GUI server will log each object sent over to the    |
|                                 | front-end. (The console gets flooded, so does the log. Use sparingly.                           |
| config.json                     | The main config file of the GUI. There are four main options listed                             |
|                                 | **guiserver**: This lists the GUI server's options. The 'ip':'port' under this refers to the IP |
|                                 | your browser should navigate to in order to view the GUI. 'maxcalls' refers to your default num-|
|                                 | ber of reference calls. 'refreshInterval' is the frequency in which the front end requests data |
|                                 | from the back-end. Use this option to tweak the 'loading' time of the GUI. (Note that for lower |
|                                 | values, your browser may take up more of reseource).                                            |
|                                 | **scale action**: The 'ip' nested under this is the IP to which the GUI server send the request |
|                                 | to scale actions. Typically this is the main CIC. Note, if the GUI server finds out that this is|
|                                 | *not* the main CIC IP, it will automatically detect and update the config file with the main CIC|
|                                 | IP. If for some reason it fails to do so, you can always set it manually. 'scriptpath' option   |
|                                 | must have the correct script path in the main CIC to send the sclare requests to.               |
|                                 | The "user" and "pw" are the username and password for making a secure shell connection to the   |
|                                 | host where scale request must be sent.                                                          |
|                                 | **ssh**: Contains the IP and SSH credentials of the node where the commands "nova-service list" |
|                                 | and "nova list" commands are executed.                                                          |
|                                 | "fetchinterval" sets the interval in seconds between the execution of two consecutive commands  |
|                                 | in the node. Example: "nova service-list" (wait fetchinterval) "nova service list" ...          |
|                                 | **ssh_call_info**: Holds the IP and SSH credentials of the node where the session load is       |
|                                 | fetched from.                                                                                   |
| appViewConfigSet.py             | ./appViewConfigSet.py \<regexp_1> \<regexp_2> ... \<regexp_n> \<true or false>                      |
|                                 | Sets all the VM names matching the regexes in the parameters 2 to n-1 to true. That is they will|
|                                 | have both 'isDemoCase' and 'visibility' set to true or false depending on what you pass.        | 
|                                 | ./appViewConfigSet.py -r                                                                        |
|                                 | Resets 'isDemoCase':false, 'visibility' true for all VMs                                        |
| html/gui_config.json            | Automatically generated config file for the GUI. if the values are changed here, the changes    |
|                                 | will affect the GUI when refresh the page is reloaded/refreshed. Does not require to restart the|
|                                 | GUI server.                                                                                     |
| html/appViewConfig.json         | The config file containing the option to set demo case and determine the visibility of each VM. |
|                                 | Is edited by the 'appViewConfigSet.py' script to perform batch operation. Can be updated        |
|                                 | manually as well to achieve the same effect. Reload the GUI page to see the effects.            |
-------------------------------------------------------------------------------------------------------------------------------------

# Freeway-Traffic-Simulator

This traffic simulator can simulate the traffic on a freeway in a time range. The freeway here is chosen to be I210 in California. The data is collected on  March 04, 2019. The simulation is based on [Eclipse SUMO - Simulation of Urban MObility](https://www.eclipse.org/sumo/) and [TraCI](https://sumo.dlr.de/pydoc/traci.html) packages.

To run the simulator, simply run **runner.py** using command: 

```cmd
python runner.py --begin_time 16 --end_time 17
```

You can turn off the gui of SUMO by adding option --nogui to the command.

#### Note: 

If you want to make the finding edge function more precise. You can manually rename the edges you want to find and make slight modification to the find_nearest_edge function to find them precisely.

If you want to use a different road map, make sure to embed geological information within it and that it matches with the station data.
from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import optparse
import random
import pandas as pd
import sumolib
import pyproj
import rtree
import time
import re
import traci.constants as tc

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary  # noqa
import traci  # noqa


def find_nearest_edge(net, lon, lat, type="", radius=1000):
    # print("lon, lat: ", lon, lat)
    x, y = net.convertLonLat2XY(lon, lat)
    # print("x, y: ", x, y)
    edges = net.getNeighboringEdges(x, y, radius)
    # print("Edges: ", edges)
    # pick the closest edge
    distancesAndEdges = []
    if len(edges) > 0:
        if type == "" or type == "ML":
            distancesAndEdges = sorted([(dist, edge) for edge, dist in edges], key=lambda foo: foo[0])
        elif type == "OR":
            distancesAndEdges = sorted([(dist, edge) for edge, dist in edges if "ONRAMP" in edge.getID()], key=lambda foo: foo[0])
        elif type == "FR":
            distancesAndEdges = sorted([(dist, edge) for edge, dist in edges if "OFFRAMP" in edge.getID()], key=lambda foo: foo[0])
        else:
            print("[Error: Edge Type Unrecognizable]")
            exit()
        if not distancesAndEdges:
            print("\n")
            print(x, y)
            for edge, dist in edges:
                print(edge.getID())
            distancesAndEdges = sorted([(dist, edge) for edge, dist in edges], key=lambda foo: foo[0])
        dist, closestEdge = distancesAndEdges[0]
        # print(distancesAndEdges)
        return closestEdge
    else:
        print("[Error: No Edge Found]")
        exit()


def find_upstream_mlstation(df):
    """
    EFFECT: Return a dictionary whose keys are Off-Ramp Stations and Values are the nearest upstream Non-Ramp stations
    REQUIRE: df is the dataframe of real data
    """
    stations = pd.DataFrame(df.groupby(by="station_id")).set_index(0)
    fr_pm = {}
    for i in range(len(stations)):
        if stations.iloc[i, 0]['lane_type'].iloc[0] == "FR":
            abs_pm = stations.iloc[i, 0]['abs_pm'].iloc[0]
            fr_pm[stations.iloc[i, 0]['station_id'].iloc[0]] = abs_pm
    # print(fr_pm)
    # print(len(fr_pm))
    station_pm = {}
    for i in range(len(stations)):
        abs_pm = stations.iloc[i, 0]['abs_pm'].iloc[0]
        station_pm[stations.iloc[i, 0]['station_id'].iloc[0]] = abs_pm
    # print(station_pm)
    fr_nearest_station = {}
    for fr in fr_pm:
        nearest_station = max([(station_id, abs_pm) for station_id, abs_pm in station_pm.items() if (
                abs_pm < fr_pm[fr] and stations[1].loc[station_id]['lane_type'].iloc[0] != "OR" and
                stations[1].loc[station_id]['lane_type'].iloc[0] != "FR")], key=lambda x: x[1])
        fr_nearest_station[fr] = nearest_station[0]
    # print(fr_nearest_station)
    for fr in fr_nearest_station:
        if stations[1].loc[fr_nearest_station[fr]]['lane_type'].iloc[0] == "OR" or \
                stations[1].loc[fr_nearest_station[fr]]['lane_type'].iloc[0] == "FR":
            print("[Error: No Main Line Found Before Off-Ramp]")
            exit()
    return fr_nearest_station


def generate_routefile(df, begin_time=16, end_time=20):
    net = sumolib.net.readNet('osm.net.xml')
    radius = 0.1

    random.seed(42)  # make tests reproducible
    N = df.shape[0]
    total_timestamp = 288  # number of time steps (5min per timestamp per day 60 * 24 / 5 = 288)
    ml = 3 / 4
    with open("test.rou.xml", "w") as routes:
        print("""<routes>
    <vType id="ml" accel="1.6" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="74" \
    guiShape="passenger"/>
        """, file=routes)
        ml_start = df[df['abs_pm'] == min(df['abs_pm'])]['station_id'].iloc[0]
        ml_end = df[df['abs_pm'] == max(df['abs_pm'])]['station_id'].iloc[0]
        ml_end_lat = df[df['abs_pm'] == max(df['abs_pm'])]['latitude'].iloc[0]
        ml_end_lon = df[df['abs_pm'] == max(df['abs_pm'])]['longitude'].iloc[0]
        ml_end_edge = find_nearest_edge(net, ml_end_lon, ml_end_lat)
        print("{} flows to generate...".format(N))
        for i in range(N):
            if df.loc[i, 'timestamp'] < begin_time * 6 or df.loc[i, 'timestamp'] >= end_time * 6:
                continue
            if df.loc[i, 'station_id'] == ml_start or df.loc[i, 'lane_type'] == "OR":
                # if df.loc[i, 'station_id'] == ml_start:
                # if df.loc[i, 'lane_type'] == "OR":
                if df.loc[i, 'total_flow'] == 0:
                    continue
                # if df.loc[i, 'station_id'] != 718214:
                #     continue
                closestEdge = find_nearest_edge(net, df.loc[i, 'longitude'], df.loc[i, 'latitude'], "OR")
                station_id = df.loc[i, 'station_id']
                total_flow = df.loc[i, 'total_flow']
                begin = df.loc[i, 'timestamp'] - begin_time * 6
                end = begin + 1
                departLane = "random" if df.loc[i, 'lane_type'] != 'OR' else "0"
                print(
                    """   <flow id="station_{}_to_{}_at_{}" begin="{}" end="{}" number="{}" from="{}" to="{}" type="ml" departLane="{}"/>""".format(
                        station_id, ml_end, begin,
                        begin * 60 * 5,
                        end * 60 * 5,
                        int(total_flow),
                        closestEdge.getID(),
                        ml_end_edge.getID(),
                        departLane
                    ), file=routes)
        print("</routes>", file=routes)
        print("Route File Generated Successfully!")


def find_split_ratio(df, fr_nearest_station):
    fr_split_ratios = {}
    k = 0
    for fr, ml in fr_nearest_station.items():
        k += 1
        #     print(df[df['station_id']==fr]['total_flow'])
        #     print(df[df['station_id']==ml]['total_flow'])
        #     print(df[df['station_id']==fr]['total_flow'].divide(df[df['station_id']==ml]['total_flow'].values))
        #     print(df[df['station_id']==ml])
        temp = pd.Series([0] * 48, index=list(range(0, 48)), name='split_ratio')
        # update on half-hour basis
        for i in range(0, 48):
            if sum(df[df['station_id'] == ml]['total_flow'].values[i:i + 6]) == 0:
                temp.loc[i] = 0
                continue
            temp.loc[i] = sum(df[df['station_id'] == fr]['total_flow'].values[i:i + 6]) / sum(
                df[df['station_id'] == ml]['total_flow'].values[i:i + 6])
        fr_split_ratios[fr] = temp
    return fr_split_ratios


def run(df, begin_time=16, end_time=20):
    """execute the TraCI control loop"""
    step = 0
    start_time = time.time()

    net = sumolib.net.readNet('osm.net.xml')
    fr_ml = find_upstream_mlstation(df)
    fr = {fr_station: find_nearest_edge(net,
                                        df[df['station_id'] == fr_station]['longitude'].iloc[0],
                                        df[df['station_id'] == fr_station]['latitude'].iloc[0],
                                        type="FR")
          for fr_station in fr_ml.keys()}
    ml = {ml_station: find_nearest_edge(net,
                                        df[df['station_id'] == ml_station]['longitude'].iloc[0],
                                        df[df['station_id'] == ml_station]['latitude'].iloc[0])
          for ml_station in list(set(fr_ml.values()))}
    split_ratio = find_split_ratio(df, fr_ml)

    while traci.simulation.getTime() < min(86400, (end_time - begin_time) * 60 * 30):
        for station in fr:
            vehicle_ids = traci.edge.getLastStepVehicleIDs(ml[fr_ml[station]].getID())
            for vehicle_id in vehicle_ids:
                if random.random() < split_ratio[station].iloc[begin_time + int(step / 60 / 30)]:
                    traci.vehicle.changeTarget(vehicle_id, fr[station].getID())

        traci.simulationStep()

        step += 1
        # print(traci.junction.getContextSubscriptionResults(junctionID))
        if step % 1000 == 0:
            print("Executing Step {}".format(step), ", Time Elapsed: %.2fs" % (time.time() - start_time))

    traci.close()
    sys.stdout.flush()


def get_options():
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="run the commandline version of sumo")
    options, args = optParser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()

    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')

    begin_time = 16
    end_time = 18

    df = pd.read_csv('data/0304.csv', parse_dates=['timestamp']).fillna(0)
    initial = df['timestamp'].iloc[0].value
    df['timestamp'] = df['timestamp'].apply(lambda x: int((x.value - initial) / 10e10) / 3)
    df.sort_values('timestamp', inplace=True, ignore_index=True)

    generate_routefile(df, begin_time, end_time)

    traci.start([sumoBinary, "-c", "osm.sumocfg",
                 "--tripinfo-output", "tripinfo.xml"])
    run(df, begin_time, end_time)

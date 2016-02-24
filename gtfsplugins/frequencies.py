# -*- coding: utf-8 -*-
#    This file is part of Gtfslib-python.
#
#    Gtfslib-python is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Gtfslib-python is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with gtfslib-python.  If not, see <http://www.gnu.org/licenses/>.
from gtfslib.utils import fmttime
"""
@author: Laurent GRÉGOIRE <laurent.gregoire@mecatran.com>
"""

from gtfslib.spatial import SpatialClusterizer
from collections import defaultdict

class Frequencies(object):
    """
    Analysis of departure frequencies for each stop (or stop cluster).
    Warning: This plugin is still in development, the interface may change.
    
    Parameters:
    --cluster=<dist> Cluster stops closer than <dist> meters.
    --alldates       To print frequencies on all filtered dates.
                     Otherwise takes date with max departures only (default).
    
    Examples:
    --filter="CalendarDate.date=='2016-01-22'"
      For all stops at a given date
    --filter="Stop.stop_name=='Villenouvelle'"
      For one stop at all dates
    --filter="(Route.route_short_name=='R1') & (CalendarDate.date=='2016-01-22')"
      For all stops of a single route at a given date
    """

    def __init__(self):
        pass

    def run(self, context, cluster=0, alldates=False, **kwargs):
        cluster_meters = float(cluster)

        print("Loading stops...")
        stops = set()
        sc = SpatialClusterizer(cluster_meters)
        for stop in context.dao().stops(fltr=context.args.filter):
            sc.add_point(stop)
            stops.add(stop)
        print("Loaded %d stops. Clusterize..." % (len(stops)))
        sc.clusterize()
        print("Aggregated in %d clusters" % (len(sc.clusters())))
        
        print("Loading calendar dates...")
        dates = set(context.dao().calendar_dates_date(fltr=context.args.filter))
        print("Loaded %d dates" % (len(dates)))
        
        print("Processing trips...")
        departures_by_clusters = defaultdict(lambda : defaultdict(list))
        ntrips = 0
        for trip in context.dao().trips(fltr=context.args.filter, prefetch_stops=True, prefetch_calendars=True):
            for stop_time in trip.stop_times:
                if not stop_time.departure_time:
                    continue
                if not stop_time.stop in stops:
                    continue
                cluster = sc.cluster_of(stop_time.stop)
                departures_by_dates = departures_by_clusters[cluster]
                for date in trip.calendar.dates:
                    if date.as_date() not in dates:
                        continue
                    departures_by_dates[date.as_date()].append(stop_time)
            if ntrips % 1000 == 0:
                print("%d trips..." % (ntrips))
            ntrips += 1
        for cluster, departures_by_dates in departures_by_clusters.items():
            print("Cluster of stops:")
            for stop in cluster.items:
                print("    * %s / %s" % (stop.stop_id, stop.stop_name))
            if alldates:
                # Print departure count for all dates
                dates_to_print = list(departures_by_dates.keys())
                dates_to_print.sort()
            else:
                # Compute the max only
                date_max = None
                dep_max = 0
                for date, departures in departures_by_dates.items():
                    ndep = len(departures)
                    if ndep >= dep_max:
                        dep_max = ndep
                        date_max = date
                if date_max is None:
                    continue
                dates_to_print = [ date_max ]
            for date in dates_to_print:
                dep_times = [dep.departure_time for dep in departures_by_dates.get(date)]
                max_hour = max(dep_times)
                min_hour = min(dep_times)
                avg_dep = len(dep_times) * 3600. / (max_hour - min_hour)
                print("    %s : %3d departures (%8s - %8s), %.02f dep/h" % (date, len(dep_times), fmttime(min_hour), fmttime(max_hour), avg_dep))
# -*- coding: utf-8 -*-
"""
@author: Laurent GRÉGOIRE <laurent.gregoire@mecatran.com>
"""

import sqlalchemy
from sqlalchemy.orm import subqueryload
from sqlalchemy.orm.session import sessionmaker

from gtfslib.converter import _convert_gtfs_model
from gtfslib.csvgtfs import Gtfs, ZipFileSource
from gtfslib.model import FeedInfo, Agency, Route, Calendar, CalendarDate, Stop, \
    Trip, StopTime
from gtfslib.orm import _Orm


class Dao(object):
    """
    Note to developer: Please do not use fancy magic, such as automatically generating methods,
    as this may break auto-complete and thus make the use of this class more difficult.
    """

    def __init__(self, db="", sql_logging=False):
        if db == "" or db is None:
            # In-memory SQLite
            connect_url = "sqlite:///"
        if "://" in db:
            # User has provided a full path
            connect_url = db
        else:
            # Assume a SQLite file
            connect_url = "sqlite:///%s" % db
        engine = sqlalchemy.create_engine(connect_url, echo=sql_logging)
        _Orm(engine)
        Session = sessionmaker(bind=engine)
        self._session = Session()

    def session(self):
        return self._session

    def add(self, obj):
        self._session.add(obj)
        
    def add_all(self, objs):
        self._session.add_all(objs)

    def delete(self, obj):
        self._session.delete(obj)
        
    def delete_feed(self, feed_id):
        self._session.query(StopTime).filter(StopTime.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(Trip).filter(Trip.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(CalendarDate).filter(CalendarDate.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(Calendar).filter(Calendar.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(Route).filter(Route.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(Stop).filter(Stop.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(Agency).filter(Agency.feed_id == feed_id).delete(synchronize_session=False)
        self._session.query(FeedInfo).filter(FeedInfo.feed_id == feed_id).delete()

    def commit(self):
        self._session.commit()
        
    def flush(self):
        self._session.flush()

    def feed(self, feed_id=""):
        return self._session.query(FeedInfo).get(feed_id)

    def feeds(self):
        return self._session.query(FeedInfo).all()

    def agency(self, agency_id, feed_id="", prefetch_routes=False):
        query = self._session.query(Agency)
        if prefetch_routes:
            query = query.options(subqueryload('routes'))
        return query.get((feed_id, agency_id))
        
    def agencies(self, fltr=None, prefetch_routes=False):
        query = self._session.query(Agency)
        if fltr is not None:
            query = query.filter(fltr)
        if prefetch_routes:
            query = query.options(subqueryload('routes'))
        return query.all()
    
    def stop(self, stop_id, feed_id="", prefetch_parent=True, prefetch_substops=True):
        query = self._session.query(Stop)
        if prefetch_parent:
            query = query.options(subqueryload('parent_station'))
        if prefetch_substops:
            query = query.options(subqueryload('sub_stops'))
        return query.get((feed_id, stop_id))
    
    def stops(self, fltr=None, trip_fltr=None, calendar_fltr=None, zone=None, prefetch_parent=True, prefetch_substops=True, batch_size=0):
        query = self._session.query(Stop)
        if fltr is not None:
            query = query.filter(fltr)
        if trip_fltr is not None:
            query = query.join(StopTime).join(Trip).filter(trip_fltr)
        if calendar_fltr is not None:
            query = query.join(StopTime).join(Trip).join(Calendar).join(CalendarDate).filter(calendar_fltr)
        if zone is not None:
            # TODO Use SQLAlchemy hybrid for this?
            query = query.filter((Stop.stop_lat >= zone.min_lat) & (Stop.stop_lat <= zone.max_lat) & (Stop.stop_lon >= zone.min_lon) & (Stop.stop_lon <= zone.max_lon))
        if prefetch_parent:
            query = query.options(subqueryload('parent_station'))
        if prefetch_substops:
            query = query.options(subqueryload('sub_stops'))
        query = query.order_by(Stop.feed_id, Stop.stop_id)
        return self._page_query(query, batch_size)
    
    def route(self, route_id, feed_id=""):
        return self._session.query(Route).get((feed_id, route_id))

    def routes(self, fltr=None, trip_fltr=None, stoptime_fltr=None, calendar_fltr=None, prefetch_trips=False):
        query = self._session.query(Route)
        if fltr is not None:
            query = query.filter(fltr)
        if trip_fltr is not None:
            query = query.join(Trip).filter(trip_fltr)
        if calendar_fltr is not None:
            query = query.join(Trip).join(Calendar).join(CalendarDate).filter(calendar_fltr)
        if stoptime_fltr is not None:
            query = query.join(Trip).join(StopTime).filter(stoptime_fltr)
        if prefetch_trips:
            query = query.options(subqueryload('trips'))
        return query.all()
    
    def calendar(self, service_id, feed_id="", prefetch_dates=True, prefetch_trips=False, prefetch_stop_times=False):
        query = self._session.query(Calendar)
        if prefetch_stop_times:
            prefetch_trips = True
        if prefetch_trips:
            loadopt = subqueryload('trips')
            if prefetch_stop_times:
                loadopt = loadopt.subqueryload('stop_times')
            query = query.options(loadopt)
        if prefetch_dates:
            query = query.options(subqueryload('dates'))
        return query.get((feed_id, service_id))
    
    def calendars(self, fltr=None, prefetch_dates=True, prefetch_trips=False):
        query = self._session.query(Calendar)
        if fltr is not None:
            query = query.join(CalendarDate).filter(fltr)
        if prefetch_dates:
            query = query.options(subqueryload('dates'))
        if prefetch_trips:
            query = query.options(subqueryload('trips'))
        return query.all()
    
    def calendar_dates(self, fltr=None):
        # TODO complete this
        query = self._session.query(CalendarDate)
        if fltr is not None:
            query = query.filter(fltr)
        return query.all()

    def trip(self, trip_id, feed_id="", prefetch_stop_times=True):
        query = self._session.query(Trip)
        if prefetch_stop_times:
            query = query.options(subqueryload('stop_times'))
        return query.get((feed_id, trip_id))
    
    def trips(self, fltr=None, calendar_fltr=None, stoptime_fltr=None, route_fltr=None, prefetch_stop_times=True, prefetch_routes=False, prefetch_stops=False, prefetch_calendars=False, batch_size=0):
        query = self._session.query(Trip)
        if fltr is not None:
            query = query.filter(fltr)
        if calendar_fltr is not None:
            query = query.join(Calendar).join(CalendarDate).filter(calendar_fltr)
        if stoptime_fltr is not None:
            query = query.join(StopTime).filter(stoptime_fltr)
        if route_fltr is not None:
            query = query.join(Route).filter(route_fltr)
        if prefetch_stops:
            prefetch_stop_times = True
        if prefetch_stop_times:
            loadopt = subqueryload('stop_times')
            if prefetch_stops:
                loadopt = loadopt.subqueryload('stop')
            query = query.options(loadopt)
        if prefetch_routes:
            query = query.options(subqueryload('route'))
        if prefetch_calendars:
            query = query.options(subqueryload('calendar'))
        query = query.order_by(Trip.feed_id, Trip.trip_id)
        return self._page_query(query, batch_size)

    def stoptimes(self, fltr=None, trip_fltr=None, route_fltr=None, calendar_fltr=None, prefetch_trips=True, prefetch_stop_times=False, batch_size=0):
        query = self._session.query(StopTime)
        if fltr is not None:
            query = query.filter(fltr)
        if trip_fltr is not None:
            query = query.join(Trip).filter(trip_fltr)
        if route_fltr is not None:
            query = query.join(Trip).join(Route).filter(route_fltr)
        if calendar_fltr is not None:
            query = query.join(Trip).join(Calendar).filter(calendar_fltr)
        if prefetch_stop_times:
            prefetch_trips = True
        if prefetch_trips:
            loadopt = subqueryload('trip')
            if prefetch_stop_times:
                loadopt = loadopt.subqueryload('stop_times')
            query = query.options(loadopt)
        query = query.order_by(StopTime.feed_id, StopTime.trip_id, StopTime.stop_sequence)
        return self._page_query(query, batch_size)

    """
    Note: If you use _page_query, please make sure you add an order_by on the query!
    See http://docs.sqlalchemy.org/en/latest/faq/ormconfiguration.html#faq-subqueryload-limit-sort
    """
    def _page_query(self, query, batch_size=0):
        def _page_generator(query, batch_size):
            offset = 0
            somedata = True
            while somedata:
                query = query.limit(batch_size).offset(offset)
                offset += batch_size
                batch = query.all()
                nrows = 0
                for row in batch:
                    nrows += 1
                    yield row
                somedata = (nrows >= batch_size)
        if batch_size <= 0:
            return query.all()
        else:
            return _page_generator(query, batch_size)
            
    def load_gtfs(self, filename, feed_id="", **kwargs):
        with Gtfs(ZipFileSource(filename)).load() as gtfs:
            _convert_gtfs_model(feed_id, gtfs, self, **kwargs)
# -*- coding: utf-8 -*-
# -----------------------------------------------------------
#
# Profile
# Copyright (C) 2012  Matthias Kuhn
# -----------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this progsram; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ---------------------------------------------------------------------

"""
Manages a graph of a wastewater network
"""
from __future__ import print_function

# pylint: disable=no-name-in-module
from builtins import str
from builtins import zip
from builtins import next
from builtins import object
from collections import defaultdict
import time
import re
from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery

from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsTolerance,
    QgsSnappingConfig,
    QgsGeometry,
    QgsDataSourceUri,
    QgsPointLocator,
    NULL
)
from qgis.gui import (
    QgsMessageBar,
    QgsMapCanvasSnappingUtils
)
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QMenu, QAction
import networkx as nx


class QgepGraphManager(QObject):
    """
    Manages a graph
    """
    reachLayer = None
    reachLayerId = -1
    nodeLayer = None
    nodeLayerId = -1
    dirty = True
    graph = None
    vertexIds = {}
    nodesOnStructure = defaultdict(list)
    # Logs performance of graph creation
    timings = []

    def __init__(self, iface):
        QObject.__init__(self)
        self.iface = iface
        self.snapper = None

    def setReachLayer(self, reach_layer):
        """
        Set the reach layer (edges)
        """
        self.reachLayer = reach_layer
        self.dirty = True

        if reach_layer:
            self.reachLayerId = reach_layer.id()
        else:
            self.reachLayerId = 0

        if self.nodeLayer and self.reachLayer:
            self.createGraph()

    def setNodeLayer(self, node_layer):
        """
        Set the node layer
        """
        self.dirty = True

        self.nodeLayer = node_layer

        if node_layer:
            self.nodeLayerId = node_layer.id()

        else:
            self.nodeLayerId = 0

        if self.nodeLayer and self.reachLayer:
            self.createGraph()

    def _addVertices(self):
        """
        Initializes the graph with the vertices from the node layer
        """
        node_provider = self.nodeLayer.dataProvider()

        features = node_provider.getFeatures()

        # Add all vertices
        for feat in features:
            fid = feat.id()

            obj_id = feat['obj_id']
            obj_type = feat['type']

            try:
                vertex = feat.geometry().asPoint()
            except AttributeError:
                # TODO Add to problem log
                pass
            self.graph.add_node(fid, point=vertex, objType=obj_type, objId=obj_id)

            self.vertexIds[str(obj_id)] = fid

        self._profile("add vertices")

    def _addEdges(self):
        """
        Initializes the graph with the edges
        """
        # Add all edges (reach)
        reach_provider = self.reachLayer.dataProvider()

        features = reach_provider.getFeatures()

        # Loop through all reaches
        for feat in features:
            try:
                obj_id = feat['obj_id']
                obj_type = feat['type']
                from_obj_id = feat['from_obj_id']
                to_obj_id = feat['to_obj_id']

                length = feat['length_calc']

                pt_id1 = self.vertexIds[from_obj_id]
                pt_id2 = self.vertexIds[to_obj_id]

                self.graph.add_edge(pt_id1, pt_id2,
                                    weight=length, feature=feat.id(),
                                    baseFeature=obj_id, objType=obj_type)
            except KeyError as e:
                print(e)

        self._profile("add edges")

    def refresh(self):
        """
        Refreshes the network graph. It will force a refresh of the materialized views in the database and then reload
        and recreate the graph.
        """
        uri = QgsDataSourceUri(self.nodeLayer.dataProvider().dataSourceUri())

        db = QSqlDatabase.addDatabase("QPSQL")  # Name of the driver -- doesn't change

        str_connect_option = "requiressl=0;service=" + uri.service()
        db.setConnectOptions(str_connect_option)

        if not db.open():
            self.iface.messageBar().pushMessage(self.tr("Warning"), db.lastError().text(),
                                                level=Qgis.Critical)

        query_template = "REFRESH MATERIALIZED VIEW qgep_od.vw_network_segment;"
        query = QSqlQuery(db)
        if not query.exec_(query_template):
            str_result = query.lastError().text()
            self.iface.messageBar().pushMessage(self.tr("Warning"), str_result, level=Qgis.Critical)
        else:
            self.iface.messageBar().pushMessage(self.tr("Success"), "vw_network_segment successfully updated",
                                                level=Qgis.Success, duration=2)

        query_template = "REFRESH MATERIALIZED VIEW qgep_od.vw_network_node;"
        query = QSqlQuery(db)
        if not query.exec_(query_template):
            str_result = query.lastError().text()
            self.iface.messageBar().pushMessage(self.tr("Warning"), str_result, level=QgsMessageBar.CRITICAL)
        else:
            self.iface.messageBar().pushMessage(self.tr("Success"), "vw_network_node successfully updated",
                                                level=Qgis.Success, duration=2)
        # recreate networkx graph
        self.graph.clear()
        self.createGraph()

    def _profile(self, name):
        """
        Adds a performance profile snapshot with the given name
        """
        spenttime = 0
        if self.timings:
            spenttime = time.clock() - self.timings[-1][1]
        self.timings.append((name, spenttime))

    # Creates a network graph
    def createGraph(self):
        """
        Create a graph
        """
        self._profile("create graph")
        # try:
        self.vertexIds = {}
        self.nodesOnStructure = defaultdict(list)
        self._profile("initiate dicts")
        self.graph = nx.DiGraph()

        self._profile("initiate graph")

        self._addVertices()
        self._addEdges()

        self.print_profile()
        self.dirty = False

    def getNodeLayer(self):
        """
        Getter for the node layer
        """
        return self.nodeLayer

    def getReachLayer(self):
        """
        Getter for the reach layer
        :return:
        """
        return self.reachLayer

    def getNodeLayerId(self):
        """
        Getter for the node layer's id
        """
        return self.nodeLayerId

    def getReachLayerId(self):
        """
        Getter for the reach layer's id
        """
        return self.reachLayerId

    def initSnapper(self):
        """
        Initialize snapper
        """
        if not self.snapper:
            self.snapper = QgsMapCanvasSnappingUtils(self.iface.mapCanvas())
            config = QgsSnappingConfig()
            config.setMode(QgsSnappingConfig.AdvancedConfiguration)
            config.setEnabled(True)
            ils = QgsSnappingConfig.IndividualLayerSettings(True, QgsSnappingConfig.VertexAndSegment,
                                                            16, QgsTolerance.Pixels)
            config.setIndividualLayerSettings(self.nodeLayer, ils)
            self.snapper.setConfig(config)

    def snapPoint(self, event) -> QgsPointLocator.Match:
        """
        Snap to a point on this network
        :param event: A QMouseEvent
        """
        clicked_point = event.pos()

        if not self.snapper:
            self.initSnapper()

        class CounterMatchFilter(QgsPointLocator.MatchFilter):
            def __init__(self):
                super().__init__()
                self.matches = list()

            def acceptMatch(self, match):
                self.matches.append(match)
                return True

        match_filter = CounterMatchFilter()
        match = self.snapper.snapToMap(clicked_point, match_filter)

        if not match.isValid() or len(match_filter.matches) == 1:
            return match
        elif len(match_filter.matches) > 1:
            point_ids = [match.featureId() for match in match_filter.matches]
            node_features = self.getFeaturesById(self.getNodeLayer(), point_ids)

            # Filter wastewater nodes
            filtered_features = {
                fid: node_features.featureById(fid)
                for fid in node_features.asDict()
                if node_features.attrAsUnicode(node_features.featureById(fid), 'type') == 'wastewater_node'
            }

            # Only one wastewater node left: return this
            if len(filtered_features) == 1:
                matches = (match for match
                           in match_filter.matches
                           if match.featureId() == next(iter(filtered_features.keys())))
                return next(matches)

            # Still not sure which point to take?
            # Are there no wastewater nodes filtered? Let the user choose from the reach points
            if not filtered_features:
                filtered_features = node_features.asDict()

            # Ask the user which point he wants to use
            actions = dict()

            menu = QMenu(self.iface.mapCanvas())

            for _, feature in list(filtered_features.items()):
                try:
                    title = feature.attribute('description') + " (" + feature.attribute('obj_id') + ")"
                except TypeError:
                    title = " (" + feature.attribute('obj_id') + ")"
                action = QAction(title, menu)
                actions[action] = match
                menu.addAction(action)

            clicked_action = menu.exec_(self.iface.mapCanvas().mapToGlobal(event.pos()))

            if clicked_action is not None:
                return actions[clicked_action]

            return QgsPointLocator.Match()

    def shortestPath(self, start_point, end_point):
        """
        Finds the shortest path from the start point
        to the end point
        :param start_point: The start node
        :param end_point:   The end node
        :return:       A (path, edges) tuple
        """
        if self.dirty:
            self.createGraph()

        try:
            path = nx.algorithms.dijkstra_path(self.graph, start_point, end_point)
            edges = [(u, v, self.graph[u][v]) for (u, v) in zip(path[0:], path[1:])]

            p = (path, edges)

        except nx.NetworkXNoPath:
            print("no path found")
            p = ([], [])

        return p

    def getTree(self, node, reverse=False):
        """
        Get
        :param node:    A start node
        :param reverse: Should the graph be reversed (upstream search)
        :return:        A list of edges
        """
        if self.dirty:
            self.createGraph()

        if reverse:
            my_graph = self.graph.reverse()
        else:
            my_graph = self.graph

        # Returns pred, weight
        pred, _ = nx.bellman_ford_predecessor_and_distance(my_graph, node)
        edges = [(v, u, my_graph[v][u]) for (u, v) in list(pred.items()) if v is not None]
        nodes = [my_graph.node[n] for n in set(list(pred.keys()) + list(pred.values())) if n is not None]

        return nodes, edges

    def getEdgeGeometry(self, edges):
        """
        Get the geometry for some edges
        :param edges:  A list of edges
        :return:       A list of polylines
        """
        cache = self.getFeaturesById(self.reachLayer, edges)
        polylines = [feat.geometry().asPolyline() for feat in list(cache.asDict().values())]
        return polylines

    # pylint: disable=no-self-use
    def getFeaturesById(self, layer, ids):
        """
        Get some features by their id
        """
        feat_cache = QgepFeatureCache(layer)
        data_provider = layer.dataProvider()

        features = data_provider.getFeatures()

        for feat in features:
            if feat.id() in ids:
                feat_cache.addFeature(feat)

        return feat_cache

    # pylint: disable=no-self-use
    def getFeaturesByAttr(self, layer, attr, values):
        """
        Get some features by an attribute value
        """
        feat_cache = QgepFeatureCache(layer)
        data_provider = layer.dataProvider()

        # Batch query and filter locally
        features = data_provider.getFeatures()

        for feat in features:
            if feat_cache.attrAsUnicode(feat, attr) in values:
                feat_cache.addFeature(feat)

        return feat_cache

    def print_profile(self):
        """
        Will print some performance profiling information
        """
        for (name, spenttime) in self.timings:
            print(name + ":" + str(spenttime))


class QgepFeatureCache(object):
    """
    A feature cache.
    The DB can be slow sometimes, so if we know, that we'll be using some features
    several times consecutively it's better to keep it in memory.
    There is no check done for maximum size. You have to care for your memory
    yourself, when using this class!
    """
    _featuresById = None
    _featuresByObjId = None
    objIdField = None
    layer = None

    def __init__(self, layer, obj_id_field='obj_id'):
        self._featuresById = {}
        self._featuresByObjId = {}
        self.objIdField = obj_id_field
        self.layer = layer

    def __getitem__(self, key):
        return self.featureById(key)

    def addFeature(self, feat):
        """
        Add a feature to the cache
        """
        self._featuresById[feat.id()] = feat
        self._featuresByObjId[self.attrAsUnicode(feat, self.objIdField)] = feat

    def featureById(self, fid):
        """
        Get a feature by its feature id
        """
        return self._featuresById[fid]

    def featureByObjId(self, obj_id):
        """
        Get a feature by its object id
        """
        return self._featuresByObjId[obj_id]

    def attrAsFloat(self, feat, attr):
        """
        Get an attribute as float
        """
        try:
            return float(self.attr(feat, attr))
        except TypeError:
            return None

    def attrAsUnicode(self, feat, attr):
        """
        Get an attribute as unicode string
        """
        return self.attr(feat, attr)

    # pylint: disable=no-self-use
    def attr(self, feat, attr):
        """
        Get an attribute
        """
        try:
            if feat[attr] == NULL:
                return None
            else:
                return feat[attr]
        except KeyError:
            QgsMessageLog.logMessage('Unknown field {}'.format(attr), 'qgep', Qgis.Critical)
            return None

    def attrAsGeometry(self, feat, attr):
        """
        Get an attribute as geometry
        """
        ewktstring = self.attrAsUnicode(feat, attr)
        # Strip SRID=21781; token, TODO: Fix this upstream
        m = re.search('(.*;)?(.*)', ewktstring)
        return QgsGeometry.fromWkt(m.group(2))

    def asDict(self):
        """
        Returns all features a s a dictionary with ids as keys
        """
        return self._featuresById

    def asObjIdDict(self):
        """
        Returns all features as a dictionary with object ids as keys.
        """
        return self._featuresById
"""
This module helps managing the QGEP project layers.
"""
from PyQt4.QtCore import (QObject, pyqtSignal)

from qgis.core import (QgsMapLayerRegistry, )


class QgepLayerNotifier(QObject):
    """
    This class sends out notification when a given set of layers is available or unavailable.
    """
    layersAvailable = pyqtSignal([dict])
    layersUnavailable = pyqtSignal()

    available = False

    def __init__(self, parent, layers):
        QObject.__init__(self, parent)
        self.layers = layers

        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)
        QgsMapLayerRegistry.instance().layersAdded.connect(self.layersAdded)

    def layersWillBeRemoved(self, _):
        """
        Gets called when a layer is removed

        @param _: The layers about to be removed
        """

        if self.available:
            for qgep_id in self.layers:
                lyrs = [lyr for (lyr_id, lyr)
                        in QgsMapLayerRegistry.instance().mapLayers().iteritems()
                        if lyr_id.startswith(qgep_id)]
                if len(lyrs) == 0:
                    self.layersUnavailable.emit()
                    self.available = False
                    return

    def layersAdded(self, _):
        """
        Gets called when a layer is added
        @param _: the layers to check
        """
        if not self.available:
            lyrlist = dict()
            for qgep_id in self.layers:
                lyr = [lyr for (lyr_id, lyr)
                       in QgsMapLayerRegistry.instance().mapLayers().iteritems()
                       if lyr_id.startswith(qgep_id)]
                if len(lyr) == 0:
                    return
                lyrlist[qgep_id] = lyr[0]

            self.available = True
            self.layersAvailable.emit(lyrlist)


# pylint: disable=too-few-public-methods
class QgepLayerManager(object):
    """
    Gives access to QGEP layers by the table name.
    """
    def __init__(self):
        pass

    @staticmethod
    def layer(qgep_id):
        """
        Get a layer by its table name. Searches for the layer in the map layer registry.
        :param qgep_id:  The id of the layer to look for
        :return:         A layer matching this id or None
        """
        lyr = [lyr for (lyr_id, lyr)
               in QgsMapLayerRegistry.instance().mapLayers().iteritems()
               if lyr_id.startswith(qgep_id)]
        if len(lyr) == 0:
            return None
        else:
            return lyr[0]
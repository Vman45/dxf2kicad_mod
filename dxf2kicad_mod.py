# refer to http://pythonhosted.org/dxfgrabber/#
# Note that there must not a line or shape overlapped
import sys
import math
import functools
from itertools import groupby

import dxfgrabber

import kicad_mod_format as kf


def _arc_point(center, radius, angle_degree):
    '''
    point defined by arc center,radius, and angel in degree
    '''
    return (center[0] + radius * math.cos(angle_degree/180*math.pi),
            center[1] + radius * math.sin(angle_degree/180*math.pi))


def _endpoints(entity):
    '''
    return a tuple of start and end points of the entity
    '''
    if "LINE" == entity.dxftype:
        return (entity.start, entity.end)
    elif "ARC" == entity.dxftype:
        return (_arc_point(entity.center, entity.radius, entity.start_angle),
                _arc_point(entity.center, entity.radius, entity.end_angle))
    else:
        raise TypeError(
            "[Error]: Unexpceted dxftype {}".format(entity.dxftype))


def _touched(p1, p2):
    distance_error = 1e-2
    return ((math.fabs(p1[0]-p2[0]) < distance_error) and
            (math.fabs(p1[1]-p2[1]) < distance_error))


def _points_in_entity(ety):

    if 'LINE' == ety.dxftype:
        return [ety.start, ety.end]
    elif 'ARC' == ety.dxftype:
        if (ety.start_angle > ety.end_angle):
            ety.end_angle += 360

        def angles(start_angle, end_angle, radius):
            '''
            yields descrete angles with step length defined by radius
            '''
            step = 1.0/ety.radius  # larger radius indicates small steps
            angle = start_angle
            while True:
                yield angle
                if (angle + step > ety.end_angle):
                    yield end_angle
                    break
                else:
                    angle += step

        return [_arc_point(ety.center, ety.radius, a) for a in
                angles(ety.start_angle, ety.end_angle, ety.radius)]
    else:
        raise TypeError(
            "[Error]: Unexpceted dxftype {}".format(ety.dxftype))


def fp_polys(layer, entities):
    '''
    yields fp_poly cmd in the layer of `entities`
    '''
    entities = list(entities)

    def _points_next_to(next_start):
        for e in entities:
            start, end = _endpoints(e)
            pts = _points_in_entity(e)
            if _touched(next_start, start):
                return pts, e
            elif _touched(next_start, end):
                pts.reverse()
                return pts, e
        return None, None

    def poly(e):
        start, next_start = _endpoints(e)
        yield [start]  # yield start points
        while True:
            pts, pts_e = _points_next_to(next_start)
            if pts:
                entities.remove(pts_e)  # remove from the set
                yield pts  # yield a list of points
                next_start = pts[-1]  # new start
            else:
                if _touched(next_start, start):
                    return
                else:
                    raise ValueError('Unclosed shape at {}'.format(next_start))

    def polys():
        while True:
            if not entities:
                return
            e = entities.pop()  # pick up one
            yield poly(e)  # yield an iterator which will yields points

    for p in polys():
        poly_points = functools.reduce(lambda x, y: x+y, p)
        # we may use *point, but since there might be more than 3 values in one
        # point, we unpack it manually
        yield kf.fp_poly(children=(kf.pts(children=(kf.xy(point[0], point[1])
                                                    for point in poly_points)),
                                   kf.layer(layer),
                                   kf.width(0.001)))


def _layer_entities(entities):
    seq = list(entities)
    seq.sort(key=lambda e: e.layer)
    groups = groupby(seq, lambda e: e.layer)
    return groups


def cmds_from_entities(entities):
    '''
    get all cmd (in kicad_mod_format) from entities which is the entities
    on all layers.
    '''
    return functools.reduce(lambda x, y: x+y,
                            (list(fp_polys(layer, entities))
                             for (layer, entities) in
                             _layer_entities(dxf.entities)))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage:\n'
              '  save to a file:   python {} '
              'inputfile.dxf > outputfile.kicad_mod\n'
              '  print to stdout:  python {} inputfile.dxf'.format(
                  sys.argv[0], sys.argv[0]))
    else:
        dxf = dxfgrabber.readfile(sys.argv[1])
        print(str(kf.Module('autogenerated',
                            children=cmds_from_entities(dxf.entities))))

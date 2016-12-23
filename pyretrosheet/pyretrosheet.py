# -*- coding: utf-8 -*-

from collections import namedtuple
import logging

class PlayerStats(object):
    """ Represents a player's statistics.
    """
    def __init__(self, player_id, player_name, team_id, batting_order, position):
        self.player_id = player_id
        self.player_name = player_name
        self.team_id = team_id
        self.position = position
        self.batting_order = batting_order

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return ((self.player_id == other.player_id) and
                    (self.player_name == other.player_name) and
                    (self.team_id == other.team_id) and
                    (self.position == other.position) and
                    (self.batting_order == other.batting_order))

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return ((self.player_id != other.player_id) or
                    (self.player_name != other.player_name) or
                    (self.team_id != other.team_id) or
                    (self.position != other.position) or
                    (self.batting_order != other.batting_order))

    def __hash__(self):
        return hash((self.player_id,
                     self.player_name,
                     self.team_id,
                     self.position,
                     self.batting_order))

    def __repr__(self):
        return '%r' % self.__dict__

class Game(object):
    """ Represents a baseball game.
    """
    def __init__(self):
        self.game_id = ''
        self.home_team_id = ''
        self.away_team_id = ''
        self.home_score = 0
        self.away_score = 0
        self.home_roster = {}
        self.away_roster = {}

IdRecord = namedtuple('IdRecord', ['game_id'])
InfoRecord = namedtuple('InfoRecord', ['key', 'value'])
StartRecord = namedtuple('StartRecord',
                         ['player_id', 'player_name', 'is_home_team', 'batting_order', 'position'])
PlayRecord = namedtuple('PlayRecord',
                        ['inning', 'is_home_team', 'player_id', 'count', 'pitches', 'play_desc'])

def attribute_stats(player, play):
    """ Attributes stats from the play to the given player.
    """
    return player

def parse_game(raw):
    """ Parses a game from a raw input string.
    """
    game = Game()
    lines = raw.splitlines()
    for line in lines:
        record = parse_record(line)

        if isinstance(record, IdRecord):
            game.game_id = record.game_id
        if isinstance(record, InfoRecord):
            if record.key == 'visteam':
                game.away_team_id = record.value
            elif record.key == 'hometeam':
                game.home_team_id = record.value
        if isinstance(record, StartRecord):
            if record.is_home_team:
                team = game.home_team_id
            else:
                team = game.away_team_id
            player = PlayerStats(record.player_id,
                                 record.player_name.translate(None, '"'),
                                 team,
                                 int(record.batting_order),
                                 int(record.position))
            if record.is_home_team:
                game.home_roster[player.player_id] = player
            else:
                game.away_roster[player.player_id] = player
        if isinstance(record, PlayRecord):
            play = parse_play(record)
            if record.is_home_team:
                player = game.home_roster[record.player_id]
                game.home_roster[record.player_id] = attribute_stats(player, play)
            else:
                player = game.away_roster[record.player_id]
                game.away_roster[record.player_id] = attribute_stats(player, play)

    return game

def parse_record(line):
    """ Parses a record from a line of input.
    """
    tokens = line.split(',')
    if tokens[0] == 'id':
        return IdRecord(tokens[1])
    if tokens[0] == 'info':
        return InfoRecord(tokens[1], tokens[2])
    if (tokens[0] == 'start') or (tokens[0] == 'sub'):
        return StartRecord(
            tokens[1],
            tokens[2],
            True if tokens[3] == '1' else False,
            tokens[4],
            tokens[5]
        )
    if tokens[0] == 'play':
        return PlayRecord(
            int(tokens[1]),
            True if tokens[2] == '1' else False,
            tokens[3],
            tokens[4],
            tokens[5],
            tokens[6]
        )
    else:
        return None

Play = namedtuple('Play', ['fielders', 'modifiers', 'runner_advances'])
OutPlay = namedtuple('OutPlay', Play._fields+('is_sf', 'is_sh', 'runner_out'))


def parse_play(record):
    """ Parses a play event.
    """
    desc = record.play_desc

    out, remain = parse_out_play(desc)
    logging.debug('basic desc: %r, remain: %s', out, remain)
    if out is not None:
        return out

    return None

def parse_out_play(desc):
    """ Attempts to parse an OutPlay from the given desc.
    """
    logging.debug('parsing basic play description from %s', desc)

    fielders, remain = parse_fielders(desc)
    runner_out, remain = parse_runner_out(remain)

    if runner_out is None:
        runner_out = 'B'

    modifiers = []
    is_sf = False
    is_sh = False
    while True:
        modifier, remain = parse_modifier(remain)
        if modifier is not None:
            modifiers.append(modifier)
            if isinstance(modifier, SacrificeFlyModifier):
                is_sf = True
            if isinstance(modifier, SacrificeHitModifier):
                is_sh = True
        else:
            break

    runner_adv, remain = parse_runner_adv(remain)

    return (OutPlay(fielders, modifiers, runner_adv, is_sf, is_sh, [runner_out]), remain)

def parse_runner_out(desc):
    """ Parses a runner out annotation.
    """
    logging.debug('attempting to parse runner out annotion from %s', desc)
    if (desc[0] == '(') and (desc[2] == ')'):
        logging.debug('found annotation for %s runner out.', desc[1])
        runner_out = desc[1]
        return runner_out, desc[3:]

    return None, desc

FlyBallModifier = namedtuple('FlyBallModifier', ['hitlocation'])
SacrificeFlyModifier = namedtuple('SacrificeFlyModifier', [])
GroundBallModifier = namedtuple('GroundBallModifier', ['hitlocation'])
GroundBallBuntModifier = namedtuple('GroundBallBuntModifier', ['hitlocation'])
SacrificeHitModifier = namedtuple('SacrificeHitModifier', [])
ForceOutModifier = namedtuple('ForceOutModifier', [])

def parse_modifier(desc):
    """ Parses out any modifiers from the desc.
    """
    logging.debug('attempting to parse a modifier from %s', desc)
    if len(desc) < 1:
        return None, desc

    if desc[0] != '/':
        # No modifiers here
        return None, desc
    
    if desc[1:3] == 'FO':
        # Sacrifice hit
        return ForceOutModifier(), desc[3:]
    if desc[1] == 'F':
        # Fly ball check for hit location
        hit_loc, remain = parse_hitlocation(desc[2:])
        return FlyBallModifier(hit_loc), remain

    if desc[1:3] == 'BG':
        logging.debug('parsed a ground ball bunt from %s', desc)
        # Ground ball check for hit location
        hit_loc, remain = parse_hitlocation(desc[3:])
        return GroundBallBuntModifier(hit_loc), remain

    if desc[1] == 'G':
        # Ground ball check for hit location
        hit_loc, remain = parse_hitlocation(desc[2:])
        return GroundBallModifier(hit_loc), remain

    if desc[1:3] == 'SF':
        # Sacrifice fly
        return SacrificeFlyModifier(), desc[3:]
    if desc[1:3] == 'SH':
        # Sacrifice hit
        return SacrificeHitModifier(), desc[3:]

    return None, desc

def parse_runner_adv(desc):
    """ Parses runner advancements from the desc.
    """
    logging.debug('attempting to parse runner advancements from %s', desc)

    if (len(desc) > 1) and (desc[0] == '.'):
        adv = desc[1:].split(';')
        return adv, None

    return [], desc
def parse_hitlocation(desc):
    """ Parses a hit location from the desc.
    """

    logging.debug('attempting to parse hit location from %s', desc)
    if len(desc) < 1:
        return None, desc

    i = 0
    while (i < len(desc)) and (desc[i] != '.') and (desc[i] != '/'):
        i = i + 1

    logging.debug('hit location canidate %s, remain: %s', desc[0:i], desc[i:])
    hit_loc = desc[0:i] if i > 0 else None

    return hit_loc, desc[i:]

def parse_fielders(desc):
    """ Parses out an fielders from the desc.
    """
    fielders = []
    i = 0
    for char in desc:
        try:
            fielder = int(char)
            fielders.append(fielder)
            i = i + 1
        except ValueError:
            break
    return fielders, desc[i:]

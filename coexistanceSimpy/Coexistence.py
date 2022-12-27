import csv
import os
import random
from coexistanceSimpy.logger_util import station_log
from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

import simpy

from coexistanceSimpy.Times import *

output_csv = "output_test.csv"

colors = [
    "\033[30m",
    "\033[32m",
    "\033[31m",
    "\033[33m",
    "\033[34m",
    "\033[35m",
    "\033[36m",
    "\033[37m",
]  # colors to distinguish stations in output

big_num = 100000  # some big number for quesing in peeemtive resources - big starting point

gap = True


class Channel_occupied(Exception):
    pass


@dataclass()
class Config:
    data_size: int = 1472  # size od payload in b
    cw_min: int = 15  # min cw window size
    cw_max: int = 63  # max cw window size 1023 def
    r_limit: int = 7
    mcs: int = 7


@dataclass()
class Config_NR:
    deter_period: int = 16  # time used for waiting in prioritization period, microsec
    observation_slot_duration: int = 9  # observation slot in mikros
    synchronization_slot_duration: int = 1000  # synchronization slot lenght in mikros
    max_sync_slot_desync: int = 1000
    min_sync_slot_desync: int = 0
    # channel access class related:
    M: int = 3  # amount of observation slots to wait after deter perion in prioritization period
    cw_min: int = 15
    cw_max: int = 63
    mcot: int = 6  # max ocupancy time


def random_sample(max, number, min_distance=0):  # func used to desync gNBs
    # returns number * elements <0, max>
    samples = random.sample(range(max - (number - 1) * (min_distance - 1)), number)
    indices = sorted(range(len(samples)), key=lambda i: samples[i])
    ranks = sorted(indices, key=lambda i: indices[i])
    return [sample + (min_distance - 1) * rank for sample, rank in zip(samples, ranks)]


class Station:
    def __init__(
            self,
            env: simpy.Environment,
            name: str,
            channel: dataclass,
            config: Config = Config(),
    ):
        self.config = config
        self.times = Times(config.data_size, config.mcs)  # using Times script to get time calculations
        self.name = name  # name of the station
        self.env = env  # simpy environment
        self.col = random.choice(colors)  # color of output -- for future station distinction
        self.frame_to_send = None  # the frame object which is next to send
        self.succeeded_transmissions = 0  # all succeeded transmissions for station
        self.failed_transmissions = 0  # all failed transmissions for station
        self.failed_transmissions_in_row = 0  # all failed transmissions for station in a row
        self.cw_min = config.cw_min  # cw min parameter value
        self.cw_max = config.cw_max  # cw max parameter value
        self.channel = channel  # channel obj
        env.process(self.start())  # starting simulation process
        self.process = None  # waiting back off process
        self.channel.airtime_data.update({name: 0})
        self.channel.airtime_control.update({name: 0})
        self.first_interrupt = False
        self.back_off_time = 0
        self.start = 0

    def start(self):
        while True:
            self.frame_to_send = self.generate_new_frame()
            was_sent = False
            while not was_sent:
                self.process = self.env.process(self.wait_back_off())
                yield self.process
                # self.process = None
                was_sent = yield self.env.process(self.send_frame())
                # self.process = None

    def wait_back_off(self):
        # global start
        self.back_off_time = self.generate_new_back_off_time(
            self.failed_transmissions_in_row)  # generating the new Back Off time

        while self.back_off_time > -1:
            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req
                self.back_off_time += Times.t_difs  # add DIFS time
                station_log(self, f"Starting to wait backoff (with DIFS): ({self.back_off_time})u...")
                self.first_interrupt = True
                self.start = self.env.now  # store the current simulation time
                self.channel.back_off_list.append(self)  # join the list off stations which are waiting Back Offs

                yield self.env.timeout(self.back_off_time)  # join the environment action queue

                station_log(self, f"Backoff waited, sending frame...")
                self.back_off_time = -1  # leave the loop

                self.channel.back_off_list.remove(self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                if self.first_interrupt and self.start is not None:
                    # tak jest po mojemu:
                    station_log(self, "Waiting was interrupted, waiting to resume backoff...")
                    all_waited = self.env.now - self.start
                    if all_waited <= Times.t_difs:
                        self.back_off_time -= Times.t_difs
                        station_log(self,
                                    f"Interupted in DIFS ({Times.t_difs}), backoff {self.back_off_time}, already waited: {all_waited}")
                    else:
                        back_waited = all_waited - Times.t_difs
                        slot_waited = int(back_waited / Times.t_slot)
                        self.back_off_time -= ((slot_waited * Times.t_slot) + Times.t_difs)
                        station_log(self,
                                    f"Completed slots(9us) {slot_waited} = {(slot_waited * Times.t_slot)}  plus DIFS time {Times.t_difs}")
                        station_log(self,
                                    f"Backoff decresed by {((slot_waited * Times.t_slot) + Times.t_difs)} new Backoff {self.back_off_time}")
                    self.first_interrupt = False

    def send_frame(self):
        self.channel.tx_list.append(self)  # add station to currently transmitting list
        res = self.channel.tx_queue.request(
            priority=(big_num - self.frame_to_send.frame_time))  # create request basing on this station frame length

        try:
            result = yield res | self.env.timeout(
                0)  # try to hold transmitting lock(station with the longest frame will get this)
            if res not in result:  # check if this station got lock, if not just wait you frame time
                raise simpy.Interrupt("There is a longer frame...")

            with self.channel.tx_lock.request() as lock:  # this station has the longest frame so hold the lock
                yield lock

                for station in self.channel.back_off_list:  # stop all station which are waiting backoff as channel is not idle
                    if station.process.is_alive:
                        station.process.interrupt()
                for gnb in self.channel.back_off_list_NR:  # stop all station which are waiting backoff as channel is not idle
                    if gnb.process.is_alive:
                        gnb.process.interrupt()

                station_log(self, f'Starting sending frame: {self.frame_to_send.frame_time}')

                yield self.env.timeout(self.frame_to_send.frame_time)  # wait this station frame time
                self.channel.back_off_list.clear()  # channel idle, clear backoff waiting list
                was_sent = self.check_collision()  # check if collision occurred

                if was_sent:  # transmission successful
                    self.channel.airtime_control[self.name] += self.times.get_ack_frame_time()
                    yield self.env.timeout(self.times.get_ack_frame_time())  # wait ack
                    self.channel.tx_list.clear()  # clear transmitting list
                    self.channel.tx_list_NR.clear()
                    self.channel.tx_queue.release(res)  # leave the transmitting queue
                    return True

                # there was collision
                self.channel.tx_list.clear()  # clear transmitting list
                self.channel.tx_list_NR.clear()
                self.channel.tx_queue.release(res)  # leave the transmitting queue
                self.channel.tx_queue = simpy.PreemptiveResource(self.env,
                                                                 capacity=1)  # create new empty transmitting queue
                yield self.env.timeout(self.times.ack_timeout)  # simulate ack timeout after failed transmission
                return False

        except simpy.Interrupt:  # this station does not have the longest frame, waiting frame time
            yield self.env.timeout(self.frame_to_send.frame_time)

        was_sent = self.check_collision()

        if was_sent:  # check if collision occurred
            station_log(self, f'Waiting for ACK time: {self.times.get_ack_frame_time()}')
            yield self.env.timeout(self.times.get_ack_frame_time())  # wait ack
        else:
            station_log(self, "waiting ack timeout slave")
            yield self.env.timeout(Times.ack_timeout)  # simulate ack timeout after failed transmission
        return was_sent

    def check_collision(self):  # check if the collision occurred

        if (len(self.channel.tx_list) + len(self.channel.tx_list_NR)) > 1 or (
                len(self.channel.tx_list) + len(self.channel.tx_list_NR)) == 0:
            self.sent_failed()
            return False
        else:
            self.sent_completed()
            return True

    def generate_new_back_off_time(self, failed_transmissions_in_row):
        upper_limit = (pow(2, failed_transmissions_in_row) * (
                self.cw_min + 1) - 1)  # define the upper limit basing on  unsuccessful transmissions in the row
        upper_limit = (
            upper_limit if upper_limit <= self.cw_max else self.cw_max)  # set upper limit to CW Max if is bigger then this parameter
        back_off = random.randint(0, upper_limit)  # draw the back off value
        self.channel.backoffs[back_off][self.channel.n_of_stations] += 1  # store drawn value for future analyzes
        return back_off * self.times.t_slot

    def generate_new_frame(self):
        # frame_length = self.times.get_ppdu_frame_time()
        frame_length = 5400
        return Frame(frame_length, self.name, self.col, self.config.data_size, self.env.now)

    def sent_failed(self):
        station_log(self, "There was a collision")
        self.frame_to_send.number_of_retransmissions += 1
        self.channel.failed_transmissions += 1
        self.failed_transmissions += 1
        self.failed_transmissions_in_row += 1
        station_log(self, self.channel.failed_transmissions)
        if self.frame_to_send.number_of_retransmissions > self.config.r_limit:
            self.frame_to_send = self.generate_new_frame()
            self.failed_transmissions_in_row = 0

    def sent_completed(self):
        station_log(self, f"Successfully sent frame, waiting ack: {self.times.get_ack_frame_time()}")
        self.frame_to_send.t_end = self.env.now
        self.frame_to_send.t_to_send = (self.frame_to_send.t_end - self.frame_to_send.t_start)
        self.channel.succeeded_transmissions += 1
        self.succeeded_transmissions += 1
        self.failed_transmissions_in_row = 0
        self.channel.bytes_sent += self.frame_to_send.data_size
        self.channel.airtime_data[self.name] += self.frame_to_send.frame_time
        return True


# Gnb -- mirroring station
class Gnb:
    def __init__(
            self,
            env: simpy.Environment,
            name: str,
            channel: dataclass,
            config_nr: Config_NR = Config_NR(),
    ):
        self.config_nr = config_nr
        # self.times = Times(config.data_size, config.mcs)  # using Times script to get time calculations
        self.name = name  # name of the station
        self.env = env  # simpy environment
        self.col = random.choice(colors)  # color of output -- for future station distinction
        self.transmission_to_send = None  # the transmision object which is next to send
        self.succeeded_transmissions = 0  # all succeeded transmissions for station
        self.failed_transmissions = 0  # all failed transmissions for station
        self.failed_transmissions_in_row = 0  # all failed transmissions for station in a row
        self.cw_min = config_nr.cw_min  # cw min parameter value
        self.N = None  # backoff counter
        self.desync = 0
        self.next_sync_slot_boundry = 0
        self.cw_max = config_nr.cw_max  # cw max parameter value
        self.channel = channel  # channel objfirst_transmission
        env.process(self.start())  # starting simulation process
        env.process(self.sync_slot_counter())
        self.process = None  # waiting back off process
        self.channel.airtime_data_NR.update({name: 0})
        self.channel.airtime_control_NR.update({name: 0})
        self.desync_done = False
        self.first_interrupt = False
        self.back_off_time = 0
        self.time_to_next_sync_slot = 0
        self.waiting_backoff = False
        self.start_nr = 0

    def start(self):

        # yield self.env.timeout(self.desync)
        while True:
            # self.transmission_to_send = self.gen_new_transmission()
            was_sent = False
            while not was_sent:
                if gap:
                    self.process = self.env.process(self.wait_back_off_gap())
                    yield self.process
                    was_sent = yield self.env.process(self.send_transmission())
                else:
                    self.process = self.env.process(self.wait_back_off())
                    yield self.process
                    was_sent = yield self.env.process(self.send_transmission())

    def wait_back_off_gap(self):
        self.back_off_time = self.generate_new_back_off_time(self.failed_transmissions_in_row)
        # adding pp to the backoff timer
        m = self.config_nr.M
        prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration
        self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure

        while self.back_off_time > -1:
            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req

                self.time_to_next_sync_slot = self.next_sync_slot_boundry - self.env.now

                station_log(self,
                            f'Backoff = {self.back_off_time} , and time to next slot: {self.time_to_next_sync_slot}')
                while self.back_off_time >= self.time_to_next_sync_slot:
                    self.time_to_next_sync_slot += self.config_nr.synchronization_slot_duration
                    station_log(self,
                                f'Backoff > time to sync slot: new time to next possible sync +1000 = {self.time_to_next_sync_slot}')

                gap_time = self.time_to_next_sync_slot - self.back_off_time
                station_log(self, f"Waiting gap period of : {gap_time} us")
                assert gap_time >= 0, "Gap period is < 0!!!"

                yield self.env.timeout(gap_time)
                station_log(self, f"Finished gap period")

                self.first_interrupt = True

                self.start_nr = self.env.now  # store the current simulation time

                station_log(self, f'Channels in use by {self.channel.tx_lock.count} stations')

                # checking if channel if idle
                if (len(self.channel.tx_list_NR) + len(self.channel.tx_list)) > 0:
                    station_log(self, 'Channel busy -- waiting to be free')
                    with self.channel.tx_lock.request() as req:
                        yield req
                    station_log(self, 'Finished waiting for free channel - restarting backoff procedure')

                else:
                    station_log(self, 'Channel free')
                    station_log(self, f"Starting to wait backoff: ({self.back_off_time}) us...")
                    self.channel.back_off_list_NR.append(self)  # join the list off stations which are waiting Back Offs
                    self.waiting_backoff = True

                    yield self.env.timeout(self.back_off_time)  # join the environment action queue

                    station_log(self, f"Backoff waited, sending frame...")
                    self.back_off_time = -1  # leave the loop
                    self.waiting_backoff = False

                    self.channel.back_off_list_NR.remove(
                        self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                station_log(self, "Waiting was interrupted")
                if self.first_interrupt and self.start is not None and self.waiting_backoff is True:
                    station_log(self, "Backoff was interrupted, waiting to resume backoff...")
                    already_waited = self.env.now - self.start_nr

                    if already_waited <= prioritization_period_time:
                        self.back_off_time -= prioritization_period_time
                        station_log(self,
                                    f"Interrupted in PP time {prioritization_period_time}, backoff {self.back_off_time}")
                    else:
                        slots_waited = int(
                            (already_waited - prioritization_period_time) / self.config_nr.observation_slot_duration)
                        # self.back_off_time -= already_waited  # set the Back Off to the remaining one
                        self.back_off_time -= ((
                                                       slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time)
                        station_log(self,
                                    f"Completed slots(9us) {slots_waited} = {(slots_waited * self.config_nr.observation_slot_duration)}  plus PP time {prioritization_period_time}")
                        station_log(self,
                                    f"Backoff decresed by {(slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time} new Backoff {self.back_off_time}")

                    # log(self, f"already waited {already_waited} Backoff us, new Backoff {self.back_off_time}")
                    self.back_off_time += prioritization_period_time  # addnin new PP before next weiting
                    self.first_interrupt = False
                    self.waiting_backoff = False

    def wait_back_off(self):
        # Wait random number of slots N x OBSERVATION_SLOT_DURATION us
        global start
        self.back_off_time = self.generate_new_back_off_time(self.failed_transmissions_in_row)
        m = self.config_nr.M
        prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration

        while self.back_off_time > -1:

            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req

                self.first_interrupt = True
                self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure
                station_log(self, f"Starting to wait backoff (with PP): ({self.back_off_time}) us...")
                start = self.env.now  # store the current simulation time
                self.channel.back_off_list_NR.append(self)  # join the list off stations which are waiting Back Offs

                yield self.env.timeout(self.back_off_time)  # join the environment action queue

                station_log(self, f"Backoff waited, sending frame...")
                self.back_off_time = -1  # leave the loop

                self.channel.back_off_list_NR.remove(self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                station_log(self, "Backoff was interrupted, waiting to resume backoff...")
                if self.first_interrupt and start is not None:
                    already_waited = self.env.now - start

                    if already_waited <= prioritization_period_time:
                        self.back_off_time -= prioritization_period_time
                        station_log(self,
                                    f"Interrupted in PP time {prioritization_period_time}, backoff {self.back_off_time}")
                    else:
                        slots_waited = int(
                            (already_waited - prioritization_period_time) / self.config_nr.observation_slot_duration)
                        # self.back_off_time -= already_waited  # set the Back Off to the remaining one
                        self.back_off_time -= ((
                                                       slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time)
                        station_log(self,
                                    f"Completed slots(9us) {slots_waited} = {(slots_waited * self.config_nr.observation_slot_duration)}  plus PP time {prioritization_period_time}")
                        station_log(self,
                                    f"Backoff decresed by {(slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time} new Backoff {self.back_off_time}")

                    self.first_interrupt = False
                    self.waiting_backoff = False

    def sync_slot_counter(self):
        # Process responsible for keeping the next sync slot boundry timestamp
        self.desync = random.randint(self.config_nr.min_sync_slot_desync, self.config_nr.max_sync_slot_desync)
        self.next_sync_slot_boundry = self.desync
        station_log(self, f"Selected random desync to {self.desync} us")
        yield self.env.timeout(self.desync)  # waiting randomly chosen desync time
        while True:
            self.next_sync_slot_boundry += self.config_nr.synchronization_slot_duration
            station_log(self, f"Next synch slot boundry is: {self.next_sync_slot_boundry}")
            yield self.env.timeout(self.config_nr.synchronization_slot_duration)

    def send_transmission(self):
        self.channel.tx_list_NR.append(self)  # add station to currently transmitting list
        self.transmission_to_send = self.gen_new_transmission()
        res = self.channel.tx_queue.request(priority=(
                big_num - self.transmission_to_send.transmission_time))  # create request basing on this station frame length

        try:
            result = yield res | self.env.timeout(
                0)  # try to hold transmitting lock(station with the longest frame will get this)

            if res not in result:  # check if this station got lock, if not just wait you frame time
                raise simpy.Interrupt("There is a longer frame...")

            with self.channel.tx_lock.request() as lock:  # this station has the longest frame so hold the lock
                yield lock

                for station in self.channel.back_off_list:  # stop all station which are waiting backoff as channel is not idle
                    if station.process.is_alive:
                        station.process.interrupt()
                for gnb in self.channel.back_off_list_NR:  # stop all station which are waiting backoff as channel is not idle
                    if gnb.process.is_alive:
                        gnb.process.interrupt()

                station_log(self, f'Transmission will be for: {self.transmission_to_send.transmission_time} time')

                yield self.env.timeout(self.transmission_to_send.transmission_time)

                self.channel.back_off_list_NR.clear()  # channel idle, clear backoff waiting list
                was_sent = self.check_collision()  # check if collision occurred

                if was_sent:  # transmission successful
                    self.channel.airtime_control_NR[self.name] += self.transmission_to_send.rs_time
                    station_log(self, f"adding rs time to control data: {self.transmission_to_send.rs_time}")
                    self.channel.airtime_data_NR[self.name] += self.transmission_to_send.airtime
                    station_log(self, f"adding data airtime to data: {self.transmission_to_send.airtime}")
                    self.channel.tx_list_NR.clear()  # clear transmitting list
                    self.channel.tx_list.clear()
                    self.channel.tx_queue.release(res)  # leave the transmitting queue
                    return True

            # there was collision
            self.channel.tx_list_NR.clear()  # clear transmitting list
            self.channel.tx_list.clear()
            self.channel.tx_queue.release(res)  # leave the transmitting queue
            self.channel.tx_queue = simpy.PreemptiveResource(self.env,
                                                             capacity=1)  # create new empty transmitting queue
            # yield self.env.timeout(self.times.ack_timeout)
            return False

        except simpy.Interrupt:  # this station does not have the longest frame, waiting frame time
            yield self.env.timeout(self.transmission_to_send.transmission_time)

        was_sent = self.check_collision()
        return was_sent

    def check_collision(self):  # check if the collision occurred

        if gap:
            # if (len(self.channel.tx_list) + len(self.channel.tx_list_NR)) > 1 and self.waiting_backoff is True:
            if (len(self.channel.tx_list) + len(self.channel.tx_list_NR)) > 1 or (
                    len(self.channel.tx_list) + len(self.channel.tx_list_NR)) == 0:
                self.sent_failed()
                return False
            else:
                self.sent_completed()
                return True
        else:
            if (len(self.channel.tx_list) + len(self.channel.tx_list_NR)) > 1 or (
                    len(self.channel.tx_list) + len(self.channel.tx_list_NR)) == 0:
                self.sent_failed()
                return False
            else:
                self.sent_completed()
                return True

    def gen_new_transmission(self):
        transmission_time = self.config_nr.mcot * 1000  # transforming to usec
        if gap:
            rs_time = 0
        else:
            rs_time = self.next_sync_slot_boundry - self.env.now
        airtime = transmission_time - rs_time
        return Transmission_NR(transmission_time, self.name, self.col, self.env.now, airtime, rs_time)

    def generate_new_back_off_time(self, failed_transmissions_in_row):
        # BACKOFF TIME GENERATION
        upper_limit = (pow(2, failed_transmissions_in_row) * (
                self.cw_min + 1) - 1)  # define the upper limit basing on  unsuccessful transmissions in the row
        upper_limit = (
            upper_limit if upper_limit <= self.cw_max else self.cw_max)  # set upper limit to CW Max if is bigger then this parameter
        back_off = random.randint(0, upper_limit)  # draw the back off value
        self.channel.backoffs[back_off][self.channel.n_of_stations] += 1  # store drawn value for future analyzes
        return back_off * self.config_nr.observation_slot_duration

    def sent_failed(self):
        station_log(self, "There was a collision")
        self.transmission_to_send.number_of_retransmissions += 1
        self.channel.failed_transmissions_NR += 1
        self.failed_transmissions += 1
        self.failed_transmissions_in_row += 1
        station_log(self, self.channel.failed_transmissions_NR)
        if self.transmission_to_send.number_of_retransmissions > 7:
            self.failed_transmissions_in_row = 0

    def sent_completed(self):
        station_log(self, f"Successfully sent transmission")
        self.transmission_to_send.t_end = self.env.now
        self.transmission_to_send.t_to_send = (self.transmission_to_send.t_end - self.transmission_to_send.t_start)
        self.channel.succeeded_transmissions_NR += 1
        self.succeeded_transmissions += 1
        self.failed_transmissions_in_row = 0
        return True


@dataclass()
class Frame:
    frame_time: int  # time of the frame
    station_name: str  # name of the owning it station
    col: str  # output color
    data_size: int  # payload size
    t_start: int  # generation time
    number_of_retransmissions: int = 0  # retransmissions count
    t_end: int = None  # sent time
    t_to_send: int = None  # how much time it took to sent successfully

    def __repr__(self):
        return (self.col + "Frame: start=%d, end=%d, frame_time=%d, retransmissions=%d"
                % (self.t_start, self.t_end, self.t_to_send, self.number_of_retransmissions)
                )


@dataclass()
class Transmission_NR:
    transmission_time: int
    enb_name: str  # name of the owning it station
    col: str
    t_start: int  # generation time / transmision start (including RS)
    airtime: int  # time spent on sending data
    rs_time: int  # time spent on sending reservation signal before data
    number_of_retransmissions: int = 0
    t_end: int = None  # sent time / transsmision end = start + rs_time + airtime
    t_to_send: int = None
    collided: bool = False  # true if transmission colided with another one


def run_simulation(
        number_of_stations: int,
        number_of_gnb: int,
        seed: int,
        simulation_time: int,
        config: Config,
        configNr: Config_NR,
        backoffs: Dict[int, Dict[int, int]],
        airtime_data: Dict[str, int],
        airtime_control: Dict[str, int],
        airtime_data_NR: Dict[str, int],
        airtime_control_NR: Dict[str, int],
):
    random.seed(seed)
    environment = simpy.Environment()
    channel = Channel(
        simpy.PreemptiveResource(environment, capacity=1),
        simpy.Resource(environment, capacity=1),
        number_of_stations,
        number_of_gnb,
        backoffs,
        airtime_data,
        airtime_control,
        airtime_data_NR,
        airtime_control_NR
    )
    # config_nr = Config_NR()
    # config_wifi = Config()

    for i in range(1, number_of_stations + 1):
        Station(environment, "Station {}".format(i), channel, config)

    for i in range(1, number_of_gnb + 1):
        # Gnb(environment, "Gnb {}".format(i), channel, config_nr)
        Gnb(environment, "Gnb {}".format(i), channel, configNr)

    # environment.run(until=simulation_time * 1000000) 10^6 milisekundy
    environment.run(until=simulation_time * 1000000)

    if number_of_stations != 0:
        if (channel.failed_transmissions + channel.succeeded_transmissions) != 0:
            p_coll = "{:.4f}".format(
                channel.failed_transmissions / (channel.failed_transmissions + channel.succeeded_transmissions))
        else:
            p_coll = 0
    else:
        p_coll = 0

    if number_of_gnb != 0:
        if (channel.failed_transmissions_NR + channel.succeeded_transmissions_NR) != 0:
            p_coll_NR = "{:.4f}".format(
                channel.failed_transmissions_NR / (
                        channel.failed_transmissions_NR + channel.succeeded_transmissions_NR))
        else:
            p_coll_NR = 0
    else:
        p_coll_NR = 0

    # DETAILED OUTPUTS:

    # print(
    #     f"SEED = {seed} N_stations:={number_of_stations}  CW_MIN = {config.cw_min} CW_MAX = {config.cw_max}  PCOLL: {p_coll} THR:"
    #     f" {(channel.bytes_sent * 8) / (simulation_time * 100000)} "
    #     f"FAILED_TRANSMISSIONS: {channel.failed_transmissions}"
    #     f" SUCCEEDED_TRANSMISSION {channel.succeeded_transmissions}"
    # )

    # print('stats for GNB ------------------')
    #
    # print(
    #     f"SEED = {seed} N_gnbs={number_of_gnb} CW_MIN = {config_nr.cw_min} CW_MAX = {config_nr.cw_max}  PCOLL: {p_coll_NR} "
    #     f"FAILED_TRANSMISSIONS: {channel.failed_transmissions_NR}"
    #     f" SUCCEEDED_TRANSMISSION {channel.succeeded_transmissions_NR}"
    # )

    # print('airtimes summary: Wifi, NR ---- 1)data, 2)control')
    #
    # print(channel.airtime_data)
    # print(channel.airtime_control)
    # print(channel.airtime_data_NR)
    # print(channel.airtime_control_NR)
    #
    # print("sumarizing airtime --------------")
    channel_occupancy_time = 0
    channel_efficiency = 0
    channel_occupancy_time_NR = 0
    channel_efficiency_NR = 0
    time = simulation_time * 1000000  # DEBUG

    # nodes = number_of_stations + number_of_gnb

    for i in range(1, number_of_stations + 1):
        channel_occupancy_time += channel.airtime_data["Station {}".format(i)] + channel.airtime_control[
            "Station {}".format(i)]
        channel_efficiency += channel.airtime_data["Station {}".format(i)]

    for i in range(1, number_of_gnb + 1):
        channel_occupancy_time_NR += channel.airtime_data_NR["Gnb {}".format(i)] + channel.airtime_control_NR[
            "Gnb {}".format(i)]
        channel_efficiency_NR += channel.airtime_data_NR["Gnb {}".format(i)]

    normalized_channel_occupancy_time = channel_occupancy_time / time
    normalized_channel_efficiency = channel_efficiency / time
    # print(f'Wifi occupancy: {normalized_channel_occupancy_time}')
    # print(f'Wifi efficieny: {normalized_channel_efficiency}')

    normalized_channel_occupancy_time_NR = channel_occupancy_time_NR / time
    normalized_channel_efficiency_NR = channel_efficiency_NR / time
    # print(f'Gnb occupancy: {normalized_channel_occupancy_time_NR}')
    # print(f'Gnb efficieny: {normalized_channel_efficiency_NR}')

    normalized_channel_occupancy_time_all = (channel_occupancy_time + channel_occupancy_time_NR) / time
    normalized_channel_efficiency_all = (channel_efficiency + channel_efficiency_NR) / time
    # print(f'All occupancy: {normalized_channel_occupancy_time_all}')
    # print(f'All efficieny: {normalized_channel_efficiency_all}')

    print(
        f"SEED = {seed} N_stations:={number_of_stations} N_gNB:={number_of_gnb}  CW_MIN = {config.cw_min} CW_MAX = {config.cw_max} "
        f"WiFi pcol:={p_coll} WiFi cot:={normalized_channel_occupancy_time} WiFi eff:={normalized_channel_efficiency} "
        f"gNB pcol:={p_coll_NR} gNB cot:={normalized_channel_occupancy_time_NR} gNB eff:={normalized_channel_efficiency_NR} "
        f" all cot:={normalized_channel_occupancy_time_all} all eff:={normalized_channel_efficiency_all}"
    )
    print(f" Wifi succ: {channel.succeeded_transmissions} fail: {channel.failed_transmissions}")
    print(f" NR succ: {channel.succeeded_transmissions_NR} fail: {channel.failed_transmissions_NR}")

    fairness = (normalized_channel_occupancy_time_all ** 2) / (
            2 * (normalized_channel_occupancy_time ** 2 + normalized_channel_occupancy_time_NR ** 2))

    print(f'fairness: {fairness}')
    joint = fairness * normalized_channel_occupancy_time_all
    print(f'joint: {joint}')

    write_header = True
    if os.path.isfile(output_csv):
        write_header = False
    with open(output_csv, mode='a', newline="") as result_file:
        result_adder = csv.writer(result_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        if write_header:
            result_adder.writerow([
                "Seed,WiFi,Gnb,ChannelOccupancyWiFi,ChannelEfficiencyWiFi,PcolWifi,ChannelOccupancyNR,ChannelEfficiencyNR,PcolNR,ChannelOccupancyAll,ChannelEfficiencyAll"])

        result_adder.writerow(
            [seed, config.cw_max, fairness, number_of_stations, number_of_gnb, normalized_channel_occupancy_time,
             normalized_channel_efficiency,
             p_coll,
             normalized_channel_occupancy_time_NR, normalized_channel_efficiency_NR, p_coll_NR,
             normalized_channel_occupancy_time_all, normalized_channel_efficiency_all])


@dataclass()
class TransmissionNRFbe:
    transmission_time: int
    gnb_name: str  # name of the owning it station
    col: str
    t_start: int
    airtime: int
    number_of_retransmissions: int = 0
    t_to_send: int = None  # how much time it took to sent successfully


class FBETimers:
    def __init__(self,
                 ffp: int,
                 cot: int,
                 cca_slots_num=1):
        # fixed frame period
        self.ffp = ffp
        self.observation_slot_time = 9
        self.cot = self.check_cot(cot)
        self.idle_period = ffp - self.cot
        self.cca = self.check_cca(cca_slots_num)

    def __repr__(self):
        return 'ffp : {} \n'.format(self.ffp) + 'cot : {} \n'.format(self.cot) + 'idle_period : {} \n'.format(
            self.idle_period) + 'cca : {} \n'.format(self.cca)

    def check_cot(self, cot):
        max_cot = self.ffp * 0.95
        if cot > max_cot:
            print('COT exceeded maximum range. Setting {} (95% of FFP) instead.'.format(max_cot))
            return max_cot
        return cot

    def check_cca(self, cca_slots_num):
        cca = cca_slots_num * self.observation_slot_time
        if cca > self.idle_period:
            print('CCA exceeded idle period time. Setting {} (idle period time) instead.'.format(self.idle_period))
            return self.idle_period
        return cca


class FBE(ABC):
    def __init__(self, name: str, timers: FBETimers, offset=0, logger_name='default'):
        self.name = self.__str__() + name
        self.env = None
        self.succeeded_transmissions = 0
        self.failed_transmissions = 0
        self.channel = None
        self.timers = timers
        self.process = None
        self.transmission_process = None
        self.skip_next_cot = False
        self.air_time = 0
        self.offset = offset
        self.run_with_offset = self.offset > 0
        self.logger_name = logger_name
        self.handle_sim_end = False

    @abstractmethod
    def start(self):
        pass

    def process_cca(self):
        init = self.env.now
        try:
            self.channel.cca_list_NR_FBE.append(self)
            station_log(self, 'Sensing if channel is idle')
            if self.get_curr_transmissions_list_len_sum() > 0:
                raise simpy.Interrupt("CCA interrupted!")
            yield self.env.timeout(self.timers.cca)
            self.skip_next_cot = False
            self.channel.cca_list_NR_FBE.remove(self)
        except simpy.Interrupt:
            end = self.env.now
            diff = end - init
            station_log(self, 'CCA interrupted, skipping next FFP')
            self.channel.cca_list_NR_FBE.remove(self)
            if diff == 0:
                yield self.env.timeout(self.timers.cca)
            else:
                yield self.env.timeout(diff)
            self.skip_next_cot = True

    def process_init_offset(self):
        if self.run_with_offset:
            yield self.env.timeout(self.offset)
        # Init cca process
        self.process = self.env.process(self.process_cca())
        yield self.process

    def check_collisions(self):
        lists_len_sum = self.get_curr_transmissions_list_len_sum()
        if lists_len_sum > 1 or lists_len_sum == 0:
            self.sent_failed()
            return False
        self.sent_completed()
        return True

    def send_transmission(self):
        self.channel.tx_list_NR_FBE.append(self)
        transmission_start = self.env.now
        transmission_end = transmission_start + self.timers.cot
        with self.channel.tx_lock.request() as request_token:
            try:
                station_log(self, f"Starting transmission")
                request = yield request_token | self.env.timeout(0)
                self.interrupt_cca()
                if request_token not in request:
                    self.interrupt_transmissions()
                remained_time = self.channel.simulation_time - transmission_start
                if remained_time < self.timers.cot:
                    station_log(self,
                                f"Transmission interrupted by simulation end. COT len = {self.timers.cot}. "
                                f"Time remained: {remained_time}")
                    self.handle_sim_end = True
                    transmission_end = transmission_start + remained_time
                    # When simpy env reaches sim end time whole simulation will be shut down.
                    # Handle this by waiting for 1 us less
                    yield self.env.timeout(remained_time - 1)
                else:
                    yield self.env.timeout(self.timers.cot)
                if self.get_curr_transmissions_list_len_sum() > 1:
                    station_log(self, f"Collision in channel detected after transmission")
                    self.sent_failed()
                    self.add_event_to_dict(EventType.CHANNEL_COLLISION.name, transmission_start, transmission_end)
                else:
                    self.sent_completed(remained_time)
                    self.add_event_to_dict(EventType.SUCCESSFUL_TRANSMISSION.name, transmission_start, transmission_end)

                if self.handle_sim_end is True:
                    yield self.env.timeout(1)
                self.channel.tx_list_NR_FBE.remove(self)

            except simpy.Interrupt:
                now = self.env.now
                remained_transmission_time = self.timers.cot - (now - transmission_start)
                station_log(self, f"Collision in channel detected during transmission. "
                                  f"Time to end transmission: {remained_transmission_time}")
                yield self.env.timeout(self.timers.cot)
                self.sent_failed()
                self.add_event_to_dict(EventType.CHANNEL_COLLISION.name, transmission_start, transmission_end)
                self.channel.tx_list_NR_FBE.remove(self)

    def interrupt_cca(self):
        for station in self.channel.cca_list_NR_FBE:
            if station.process.is_alive:
                station_log(self, f"Interrupting CCA process of station: {station.name}")
                station.process.interrupt()

    def interrupt_transmissions(self):
        for station in self.channel.tx_list_NR_FBE:
            if station != self and station.transmission_process.is_alive:
                station_log(self, f"Interrupting transmission process of station: {station.name}")
                station.transmission_process.interrupt()
        raise simpy.Interrupt("Collision in channel")

    def sent_failed(self):
        station_log(self, f"Transmission failed")
        self.failed_transmissions += 1
        self.channel.failed_transmissions_NR_FBE += 1

    def add_event_to_dict(self, event_type, event_start, event_end):
        self.channel.event_dict["time"].append(event_start)
        self.channel.event_dict["event_end"].append(event_end)
        self.channel.event_dict["station_name"].append(self.name)
        self.channel.event_dict["event_type"].append(event_type)

    def ffp_skip_transmission(self):
        yield self.env.process(self.skip_cot())
        yield self.env.process(self.wait_until_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def ffp_with_transmission(self):
        self.transmission_process = self.env.process(self.send_transmission())
        yield self.transmission_process
        yield self.env.process(self.wait_until_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def sent_completed(self, sim_end_air_time=None):
        station_log(self, f"Successfully sent transmission")
        if self.handle_sim_end:
            station_log(self, f"Current air time: {self.air_time}. Airtime to add: {sim_end_air_time}. "
                              f"Sum : {self.air_time + sim_end_air_time}")
            self.air_time += sim_end_air_time
            self.succeeded_transmissions += 1
        else:
            station_log(self, f"Current air time: {self.air_time}. Airtime to add: {self.timers.cot}. "
                              f"Sum : {self.air_time + self.timers.cot}")
            self.succeeded_transmissions += 1
            self.air_time += self.timers.cot
        self.channel.succeeded_transmissions_NR_FBE += 1

    def get_curr_transmissions_list_len_sum(self):
        return len(self.channel.tx_list) + len(self.channel.tx_list_NR) + len(self.channel.tx_list_NR_FBE)

    def wait_until_cca(self):
        yield self.env.timeout(self.timers.idle_period - self.timers.cca)

    def skip_cot(self):
        yield self.env.timeout(self.timers.cot)

    def set_log_name(self, log_name):
        self.logger_name = log_name

    @abstractmethod
    def get_fbe_version(self):
        pass

    def set_environment(self, env):
        self.env = env
        self.env.process(self.start())

    def set_channel(self, channel):
        self.channel = channel

    def __str__(self) -> str:
        return "FBE "

    def __repr__(self) -> str:
        return f'\n' \
               f'Offset: {self.offset} \n' \
               f'Timers: \n' \
               f'cot: {self.timers.cot} \n' \
               f'ffp: {self.timers.ffp} \n' \
               f'cca: {self.timers.cca} \n'


class StandardFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0):
        super().__init__(name, timers, offset)

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.skip_next_cot:
                yield self.env.process(self.ffp_skip_transmission())
            else:
                yield self.env.process(self.ffp_with_transmission())

    def get_fbe_version(self):
        return FBEVersion.STANDARD_FBE

    def __str__(self) -> str:
        return "Standard FBE "


def select_random_number(random_range, bottom_range=1):
    return random.randint(bottom_range, random_range)


class RandomMutingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0, max_frames_in_a_row=5, max_muted_periods=5):
        super().__init__(name, timers, offset)
        self.max_transmissions_in_a_row = max_frames_in_a_row
        self.max_muted_periods = max_muted_periods
        self.transmissions_in_a_row_to_go = -1
        self.muted_periods_to_go = 0

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.transmissions_in_a_row_to_go == 0:
                self.muted_periods_to_go = select_random_number(self.max_muted_periods)
                station_log(self,
                            f"Selecting number of muted periods. Selected number: {self.muted_periods_to_go}")
                for i in range(self.muted_periods_to_go):
                    station_log(self, f"Skipping frame... {i + 1}/{self.muted_periods_to_go}")
                    if i == self.muted_periods_to_go - 1:
                        yield self.env.process(self.ffp_skip_transmission())
                    else:
                        yield self.env.process(self.ffp_skip_transmission_without_cca())

                self.transmissions_in_a_row_to_go = -1

            if self.skip_next_cot:
                yield self.env.process(self.ffp_skip_transmission())
            else:
                if self.transmissions_in_a_row_to_go == -1:
                    self.transmissions_in_a_row_to_go = select_random_number(self.max_transmissions_in_a_row)
                    station_log(self,
                                f'Selecting number of frames which will be transmitted in the row. '
                                f'Selected number: {self.transmissions_in_a_row_to_go} ')

                station_log(self, f'Continuous frames to go: {self.transmissions_in_a_row_to_go}')
                yield self.env.process(self.ffp_with_transmission())

    def process_cca(self):
        yield from super().process_cca()
        if self.skip_next_cot:
            self.transmissions_in_a_row_to_go = -1

    def ffp_skip_transmission_without_cca(self):
        yield self.env.timeout(self.timers.ffp)

    def sent_failed(self):
        super().sent_failed()
        self.transmissions_in_a_row_to_go = -1

    def sent_completed(self, interrupted_by_simulation_end=False):
        self.transmissions_in_a_row_to_go += -1
        super().sent_completed(interrupted_by_simulation_end)

    def get_fbe_version(self):
        return FBEVersion.RANDOM_MUTING_FBE

    def __str__(self) -> str:
        return "Random-muting FBE "

    def __repr__(self) -> str:
        return super().__repr__() + \
               f'max_transmissions_in_a_row: {self.max_transmissions_in_a_row} \n' \
               f'max_muted_periodes: {self.max_muted_periods} \n'


class FloatingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0):
        super().__init__(name, timers, offset)
        self.number_of_slots = math.floor(timers.idle_period / timers.observation_slot_time) - 1
        self.pause_time_after_transmission = 0

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            yield self.env.process(self.backoff_process())
            if self.skip_next_cot:
                yield self.env.process(self.ffp_skip_transmission())
            else:
                yield self.env.process(self.ffp_with_transmission())

    def wait_random_time_before_cca(self):
        time_to_wait = select_random_number(self.number_of_slots) * self.timers.observation_slot_time
        station_log(self, f'Selected backoff before CCA : {time_to_wait}')
        self.pause_time_after_transmission = self.timers.idle_period - time_to_wait - self.timers.cca
        yield self.env.timeout(time_to_wait)

    def ffp_skip_transmission(self):
        yield self.env.timeout(self.timers.cot + self.pause_time_after_transmission)

    def ffp_with_transmission(self):
        self.transmission_process = self.env.process(self.send_transmission())
        yield self.transmission_process
        station_log(self, f'Waiting : {self.pause_time_after_transmission} before next FFP')
        yield self.env.timeout(self.pause_time_after_transmission)

    def backoff_process(self):
        yield self.env.process(self.wait_random_time_before_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def process_init_offset(self):
        if self.run_with_offset:
            yield self.env.timeout(self.offset)

    def get_fbe_version(self):
        return FBEVersion.FLOATING_FBE

    def __str__(self) -> str:
        return "Floating FBE "

    def __repr__(self) -> str:
        return super().__repr__() + \
               f'slots_num: {self.number_of_slots} \n'


class FixedMutingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0, max_number_of_muted_periods=1):
        super().__init__(name, timers, offset)
        self.muted_periods_to_go = 0
        self.max_number_of_muted_periods = max_number_of_muted_periods

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.muted_periods_to_go > 0:
                station_log(self,
                            f'Waiting muted periods after successful transmission. Muted periods to go '
                            f'{self.muted_periods_to_go}')
                if self.muted_periods_to_go == 1:
                    yield self.env.process(self.ffp_skip_transmission())
                else:
                    yield self.env.process(self.ffp_skip_transmission_without_cca())
                self.muted_periods_to_go += -1
            else:
                if self.skip_next_cot:
                    yield self.env.process(self.ffp_skip_transmission())
                else:
                    yield self.env.process(self.ffp_with_transmission())

    def ffp_skip_transmission_without_cca(self):
        yield self.env.timeout(self.timers.ffp)

    def ffp_with_transmission(self):
        self.transmission_process = self.env.process(self.send_transmission())
        yield self.transmission_process
        yield self.env.process(self.wait_until_cca())
        if self.muted_periods_to_go <= 0:
            self.process = self.env.process(self.process_cca())
            yield self.process
        else:
            yield self.env.timeout(self.timers.cca)

    def sent_completed(self, sim_end_air_time=None):
        super().sent_completed(sim_end_air_time)
        self.muted_periods_to_go = self.max_number_of_muted_periods

    def get_fbe_version(self):
        return FBEVersion.FIXED_MUTING_FBE

    def __str__(self) -> str:
        return "Fixed-muting FBE "

    def __repr__(self) -> str:
        return super().__repr__() + \
               f'max_number_of_muted_periods: {self.max_number_of_muted_periods}'


class DeterministicBackoffFBE(FBE):

    def __init__(self, name: str, timers: FBETimers,
                 offset=0,
                 maximum_number_of_retransmissions=5, init_backoff_value=3, threshold=4):
        super().__init__(name, timers, offset)
        self.retransmission_counter = 0
        self.maximum_number_of_retransmissions = maximum_number_of_retransmissions
        self.backoff_counter = 0
        self.init_backoff_value = init_backoff_value
        self.threshold = threshold
        self.interrupt_counter = 0
        self.is_interrupt_counter_incremented = False
        self.drop_frame = False
        self.incremented_during_monitor = False
        self.monitor_time = self.timers.ffp - self.timers.cca

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.backoff_counter == 0:
                self.is_interrupt_counter_incremented = False
                yield self.env.process(self.ffp_with_transmission())
            else:
                self.skip_next_cot = False
                yield self.env.process(self.ffp_skip_transmission())
            if self.drop_frame:
                station_log(self, 'Dropping frame ...')
                self.drop_frame = False
                self.select_backoff()

    def send_transmission(self):
        for db_station in self.channel.db_fbe_list:
            db_station.log_actual_backoff()
        yield from super().send_transmission()

    def process_init_offset(self):
        self.add_interrupt_counter_to_dict(True)
        if self.run_with_offset:
            yield self.env.timeout(self.offset)

        self.select_backoff()
        self.process = self.env.process(self.process_cca())
        yield self.process

    def ffp_skip_transmission(self):
        self.process = self.env.process(self.monitor_channel())
        yield self.process
        self.process = self.env.process(self.process_cca())
        yield self.process

    def monitor_channel(self):
        now = self.env.now
        try:
            self.channel.cca_list_NR_FBE.append(self)
            if self.get_curr_transmissions_list_len_sum() > 0:
                station_log(self, 'Channel monitoring failed at the beginning')
                raise simpy.Interrupt('Channel monitoring failed at the beginning')
            yield self.env.timeout(self.monitor_time)
            self.channel.cca_list_NR_FBE.remove(self)
        except simpy.Interrupt:
            end = self.env.now
            diff = end - now
            self.channel.cca_list_NR_FBE.remove(self)
            self.increment_interrupt_counter()
            self.incremented_during_monitor = True
            station_log(self, f'Incrementing interrupt_counter. '
                              f'Actual value: {self.interrupt_counter}. '
                              f'Incremented during monitor: {self.incremented_during_monitor}. '
                              f'Time to finish monitor mode: {self.monitor_time - diff}')
            yield self.env.timeout(self.monitor_time - diff)

    def increment_interrupt_counter(self):
        # if not self.is_interrupt_counter_incremented:
        self.interrupt_counter += 1
        self.is_interrupt_counter_incremented = True
        self.add_interrupt_counter_to_dict()

    def process_cca(self):
        yield from super().process_cca()
        if self.skip_next_cot:
            if not self.incremented_during_monitor:
                self.increment_interrupt_counter()
                station_log(self, f'Interrupt counter incremented after CCA. Actual value: {self.interrupt_counter}')
                self.incremented_during_monitor = False
        else:
            if self.backoff_counter > 0:
                self.backoff_counter -= 1
                station_log(self, f'Backoff counter decremented. Actual value: {self.backoff_counter}')
                self.add_backoff_to_dict(False)
                if self.backoff_counter == 0:
                    station_log(self, f'Backoff = 0. Starting transmission immediately')

    def sent_failed(self):
        super().sent_failed()
        if self.retransmission_counter < self.maximum_number_of_retransmissions:
            self.retransmission_counter += 1
            station_log(self, f'Incrementing retransmission_counter to {self.retransmission_counter}')
            self.select_backoff()
        else:
            # In our case simply setting counter to 0 and restarting procedure in next ffp
            station_log(self,
                        f'Retransmission_counter exceeded maximum number of retransmissions'
                        f' {self.retransmission_counter}/{self.maximum_number_of_retransmissions}.'
                        f'Frame will be dropped...')
            self.retransmission_counter = 0
            self.drop_frame = True

    def sent_completed(self, sim_end_air_time=None):
        super().sent_completed(sim_end_air_time)
        self.retransmission_counter = 0
        self.select_backoff()

    def select_backoff(self):
        modulo = self.retransmission_counter % self.maximum_number_of_retransmissions
        if modulo < self.threshold:
            self.backoff_counter = self.init_backoff_value + self.interrupt_counter
            station_log(self,
                        f'Selected new backoff counter: {self.backoff_counter} = {self.init_backoff_value} + {self.interrupt_counter}')
            self.interrupt_counter = 0
            self.add_interrupt_counter_to_dict()
        else:
            station_log(self, f'False in r%m < threshold ({modulo}<{self.threshold})')
            top_range = self.maximum_number_of_retransmissions - 1
            self.backoff_counter = select_random_number(top_range, bottom_range=0)
            station_log(self, f'Selected new random backoff counter: {self.backoff_counter} = rand({0}, {top_range})')
        self.add_backoff_to_dict()

    def add_backoff_to_dict(self, is_init=True):
        time = self.env.now
        self.channel.db_fbe_backoff_change_dict["time"].append(time)
        self.channel.db_fbe_backoff_change_dict["backoff"].append(self.backoff_counter)
        self.channel.db_fbe_backoff_change_dict["station_name"].append(self.name)
        self.channel.db_fbe_backoff_change_dict["is_init"].append(is_init)

    def add_interrupt_counter_to_dict(self, is_init=False):
        if is_init:
            time = 0
        else:
            time = self.env.now
        self.channel.db_interrupt_counter["time"].append(time)
        self.channel.db_interrupt_counter["value"].append(self.interrupt_counter)
        self.channel.db_interrupt_counter["station_name"].append(self.name)

    def set_channel(self, channel):
        super().set_channel(channel)
        self.channel.db_fbe_list.append(self)

    def log_actual_backoff(self):
        station_log(self, f'Actual backoff log {self.backoff_counter}')

    def get_fbe_version(self):
        return FBEVersion.DETERMINISTIC_BACKOFF_FBE

    def __str__(self) -> str:
        return "Deterministic-backoff FBE "

    def __repr__(self) -> str:
        return super().__repr__() + \
               f'maximum_number_of_retransmissions: {self.maximum_number_of_retransmissions} \n' \
               f'init_backoff_value: {self.init_backoff_value} \n' \
               f'threshold: {self.threshold} \n'


def get_fbe_versions():
    return [FBEVersion.STANDARD_FBE, FBEVersion.FLOATING_FBE, FBEVersion.FIXED_MUTING_FBE, FBEVersion.RANDOM_MUTING_FBE,
            FBEVersion.DETERMINISTIC_BACKOFF_FBE]


class FBEVersion(Enum):
    STANDARD_FBE = 1
    RANDOM_MUTING_FBE = 2
    FIXED_MUTING_FBE = 3
    FLOATING_FBE = 4
    DETERMINISTIC_BACKOFF_FBE = 5


class EventType(Enum):
    SUCCESSFUL_TRANSMISSION = 1
    CHANNEL_COLLISION = 2
    CCA_INTERRUPTED = 3


@dataclass()
class Event:
    station_name: str
    event_type: EventType
    event_timestamp: int


@dataclass()
class Channel:
    tx_queue: simpy.PreemptiveResource  # lock for the stations with the longest frame to transmit
    tx_lock: simpy.Resource  # channel lock (locked when there is ongoing transmission)
    n_of_stations: int  # number of transmitting stations in the channel
    n_of_eNB: int
    backoffs: Dict[int, Dict[int, int]]
    airtime_data: Dict[str, int]
    airtime_control: Dict[str, int]
    airtime_data_NR: Dict[str, int]
    airtime_control_NR: Dict[str, int]
    simulation_time: int

    tx_list: List[Station] = field(default_factory=list)  # transmitting stations in the channel
    back_off_list: List[Station] = field(default_factory=list)  # stations in backoff phase
    tx_list_NR: List[Gnb] = field(default_factory=list)  # transmitting stations in the channel
    tx_list_NR_FBE: List[FBE] = field(default_factory=list)  # transmitting FBE stations in the channel
    back_off_list_NR: List[Gnb] = field(default_factory=list)  # stations in backoff phase
    cca_list_NR_FBE: List[FBE] = field(default_factory=list)
    event_dict: dict = field(
        default_factory=lambda: {"time": [], "event_end": [], "station_name": [], "event_type": []})
    db_fbe_backoff_change_dict: dict = field(
        default_factory=lambda: {"time": [], "backoff": [], "station_name": [], "is_init": []})
    db_interrupt_counter: dict = field(
        default_factory=lambda: {"time": [], "value": [], "station_name": []}
    )
    db_fbe_list: List[DeterministicBackoffFBE] = field(default_factory=list)
    failed_transmissions: int = 0  # total failed transmissions
    succeeded_transmissions: int = 0  # total succeeded transmissions
    bytes_sent: int = 0  # total bytes sent
    failed_transmissions_NR: int = 0  # total failed transmissions
    succeeded_transmissions_NR: int = 0  # total succeeded transmissions
    failed_transmissions_NR_FBE: int = 0  # total failed FBE transmissions
    succeeded_transmissions_NR_FBE: int = 0  # total succeeded FBE transmissions


def single_run_test(
        seeds: int,
        stations_number: int,
        gnb_number: int,
        simulation_time: int,
):
    backoffs = {key: {stations_number: 0} for key in range(63 + 1)}
    airtime_data = {"Station {}".format(i): 0 for i in range(1, stations_number + 1)}
    airtime_control = {"Station {}".format(i): 0 for i in range(1, stations_number + 1)}
    airtime_data_NR = {"Gnb {}".format(i): 0 for i in range(1, gnb_number + 1)}
    airtime_control_NR = {"Gnb {}".format(i): 0 for i in range(1, gnb_number + 1)}
    # run_simulation(stations_number, gnb_number, seeds, simulation_time, Config(payload_size, cw_min, cw_max, r_limit, mcs_value),
    #                backoffs, airtime_data, airtime_control)
    run_simulation(stations_number, gnb_number, seeds, simulation_time,
                   Config(),
                   Config_NR(),
                   backoffs, airtime_data, airtime_control, airtime_data_NR, airtime_control_NR)


if __name__ == "__main__":
    print(FBEVersion["FLOATING_FBE"])
    print(FBEVersion.FLOATING_FBE.name)


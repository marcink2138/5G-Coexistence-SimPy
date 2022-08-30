import csv
import logging
import os
import random
from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from enum import Enum

import simpy

from Times import *

output_csv = "output_test.csv"
file_log_name = f"{os.getcwd()}/logs/{datetime.today().strftime('%Y-%m-%d-%H-%M-%S')}.log"

typ_filename = "RS_coex_1sta_1wifi2.log"

logging.basicConfig(filename=file_log_name,
                    format='%(asctime)s %(message)s',
                    filemode='w')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # chose DEBUG to display stats in debug mode :)

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


# class FBELogger:
#
#     def __init__(self, is_enabled=True) -> None:
#         super().__init__()
#         if is_enabled:
#             self.file_name = f"{datetime.today().strftime('%Y-%m-%d-%H-%M-%S')}.log"
#         else:
#             self.file_name = None
#         logging.basicConfig(filename=self.file_name,
#                             format='%(asctime)s %(message)s',
#                             filemode='w')
#         self.logger = logging.getLogger()
#         self.logger.setLevel(logging.DEBUG)
#
#     def log(self, gnb, mes):
#         self.logger.info(f"Time: {gnb.env.now} Station: {gnb.name} Message: {mes}")


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


def log(gnb, mes: str) -> None:
    pass
    logger.info(
        f"Time: {gnb.env.now} Station: {gnb.name} Message: {mes}"
    )


# def log(station, mes: str):
#     logging.info(
#         f"{station.col}Time: {station.env.now} Station: {station.name} Message: {mes}"
#     )

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
        global start
        self.back_off_time = self.generate_new_back_off_time(
            self.failed_transmissions_in_row)  # generating the new Back Off time

        while self.back_off_time > -1:
            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req
                self.back_off_time += Times.t_difs  # add DIFS time
                log(self, f"Starting to wait backoff (with DIFS): ({self.back_off_time})u...")
                self.first_interrupt = True
                start = self.env.now  # store the current simulation time
                self.channel.back_off_list.append(self)  # join the list off stations which are waiting Back Offs

                yield self.env.timeout(self.back_off_time)  # join the environment action queue

                log(self, f"Backoff waited, sending frame...")
                self.back_off_time = -1  # leave the loop

                self.channel.back_off_list.remove(self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                if self.first_interrupt and start is not None:
                    # tak jest po mojemu:
                    log(self, "Waiting was interrupted, waiting to resume backoff...")
                    all_waited = self.env.now - start
                    if all_waited <= Times.t_difs:
                        self.back_off_time -= Times.t_difs
                        log(self, f"Interupted in DIFS ({Times.t_difs}), backoff {self.back_off_time}")
                    else:
                        back_waited = all_waited - Times.t_difs
                        slot_waited = int(back_waited / Times.t_slot)
                        self.back_off_time -= ((slot_waited * Times.t_slot) + Times.t_difs)
                        # self.back_off_time -= (self.env.now - start)  # set the Back Off to the remaining one
                        # self.back_off_time -= 9  # simulate the delay of sensing the channel state
                        log(self,
                            f"Completed slots(9us) {slot_waited} = {(slot_waited * Times.t_slot)}  plus DIFS time {Times.t_difs}")
                        log(self,
                            f"Backoff decresed by {((slot_waited * Times.t_slot) + Times.t_difs)} new Backoff {self.back_off_time}")
                    self.first_interrupt = False

                    # log(self, "Waiting was interrupted, waiting to resume backoff...")
                    # if self.first_interrupt and start is not None:
                    #     # log(self, "Waiting was interrupted, waiting to resume backoff...")
                    #     # if self.first_interrupt and start is not None:
                    #     #log(self, f"Bacoff time reduced by: {(self.env.now - start)}")
                    #     already_waited = self.env.now - start
                    #     slots_waited = already_waited / 9
                    #
                    #     self.back_off_time -= (slots_waited * 9)  # set the Back Off to the remaining one
                    #     self.first_interrupt = False

                    # tak jest wg DCF SimPy
                    # all_waited = self.env.now - start
                    # if all_waited <= Times.t_difs:
                    #     self.back_off_time -= Times.t_difs
                    #     log(self, f"Interupted in DIFS ({Times.t_difs})")
                    # else:
                    #     self.back_off_time -= (self.env.now - start)  # set the Back Off to the remaining one
                    #     self.back_off_time -= 9  # simulate the delay of sensing the channel state
                    # log(self, f"Already waited {(self.env.now - start)}, new backoff: {self.back_off_time}")
                    # self.first_interrupt = False

    def send_frame(self):
        self.channel.tx_list.append(self)  # add station to currently transmitting list
        res = self.channel.tx_queue.request(
            priority=(big_num - self.frame_to_send.frame_time))  # create request basing on this station frame length

        try:
            result = yield res | self.env.timeout(
                0)  # try to hold transmitting lock(station with the longest frame will get this)
            # maby lista
            # kolizja osobne lsity dla gnb i wifi
            # lista zobaczyc czy zajety kanal przez tx_list
            #
            if res not in result:  # check if this station got lock, if not just wait you frame time
                log(self, f'Inside if in {self.name}')
                raise simpy.Interrupt("There is a longer frame...")
                # yield self.env.timeout(self.frame_to_send.frame_time)
                # return False

            with self.channel.tx_lock.request() as lock:  # this station has the longest frame so hold the lock
                yield lock
                # log(self, f'{self.channel.back_off_list}')

                for station in self.channel.back_off_list:  # stop all station which are waiting backoff as channel is not idle
                    # if station.process is not None:
                    #     station.process.interrupt()
                    if station.process.is_alive:
                        station.process.interrupt()
                for gnb in self.channel.back_off_list_NR:  # stop all station which are waiting backoff as channel is not idle
                    # if gnb.process is not None:
                    #     gnb.process.interrupt()
                    if gnb.process.is_alive:
                        gnb.process.interrupt()

                log(self, f'Starting sending frame: {self.frame_to_send.frame_time}')

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
            log(self, f'Waiting for ACK time: {self.times.get_ack_frame_time()}')
            yield self.env.timeout(self.times.get_ack_frame_time())  # wait ack
        else:
            log(self, "waiting ack timeout slave")
            yield self.env.timeout(Times.ack_timeout)  # simulate ack timeout after failed transmission
        return was_sent

    def check_collision(self):  # check if the collision occurred
        # if (len(self.channel.tx_list) > 1 or len(
        #         self.channel.tx_list_NR) > 1):  # check if there was more then one station transmitting

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
        log(self, "There was a collision")
        self.frame_to_send.number_of_retransmissions += 1
        self.channel.failed_transmissions += 1
        self.failed_transmissions += 1
        self.failed_transmissions_in_row += 1
        log(self, self.channel.failed_transmissions)
        if self.frame_to_send.number_of_retransmissions > self.config.r_limit:
            self.frame_to_send = self.generate_new_frame()
            self.failed_transmissions_in_row = 0

    def sent_completed(self):
        log(self, f"Successfully sent frame, waiting ack: {self.times.get_ack_frame_time()}")
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

    def start(self):

        # yield self.env.timeout(self.desync)
        while True:
            # loop with runn proces TO DO
            # zainicjalizuj N, jako licznik ile stloów backoffu ma czekać startowo
            # tak samo zainicjalizować jakiś różny desync time :P

            # self.transmission_to_send = self.gen_new_transmission()
            was_sent = False
            while not was_sent:
                if gap:
                    # self.process = self.env.process(self.wait_prioritization_period_gap())
                    # yield self.process
                    self.process = self.env.process(self.wait_back_off_gap())
                    yield self.process
                    # self.process = None
                    was_sent = yield self.env.process(self.send_transmission())
                    # self.process = None
                else:
                    # self.process = self.env.process(self.wait_prioritization_period())
                    # yield self.process
                    self.process = self.env.process(self.wait_back_off())
                    yield self.process
                    # self.process = None
                    was_sent = yield self.env.process(self.send_transmission())
                    # self.process = None

    def wait_back_off_gap(self):
        # global start
        global start
        self.back_off_time = self.generate_new_back_off_time(self.failed_transmissions_in_row)
        # adding pp to the backoff timer
        m = self.config_nr.M
        prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration
        self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure

        while self.back_off_time > -1:
            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req

                # adding PP to Backoff
                # m = self.config_nr.M
                # prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration
                # self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure

                # self.back_off_time += prioritization_period_time
                self.time_to_next_sync_slot = self.next_sync_slot_boundry - self.env.now

                log(self, f'Backoff = {self.back_off_time} , and time to next slot: {self.time_to_next_sync_slot}')
                while self.back_off_time >= self.time_to_next_sync_slot:
                    self.time_to_next_sync_slot += self.config_nr.synchronization_slot_duration
                    log(self,
                        f'Backoff > time to sync slot: new time to next possible sync +1000 = {self.time_to_next_sync_slot}')
                    # case1 : time >= backoff -- gap istnieje lub =0
                    # case2 : time < backoff --- wtedy nie da sie odczekac
                    # musimy isc do nastepnego slotu i tam backoff --> czyli time = time + wartosc_slotu :D
                    # reszta nromalnie

                gap_time = self.time_to_next_sync_slot - self.back_off_time
                log(self, f"Waiting gap period of : {gap_time} us")
                assert gap_time >= 0, "Gap period is < 0!!!"

                yield self.env.timeout(gap_time)
                log(self, f"Finished gap period")

                # must check if the channel is free + in case 2 or more gNBs start transmitting it must drop procedure
                # not just wait till free
                self.first_interrupt = True

                start = self.env.now  # store the current simulation time

                log(self, f'Channels in use by {self.channel.tx_lock.count} stations')

                # checking if channel if idle /// mozna tez spradzac dlugoscia listy stacji ktore transmituja i to chyba bedzie lepsze
                if (len(self.channel.tx_list_NR) + len(self.channel.tx_list)) > 0:
                    # if self.channel.tx_lock.count > 0:
                    log(self, 'Channel busy -- waiting to be free')
                    with self.channel.tx_lock.request() as req:
                        yield req
                    log(self, 'Finished waiting for free channel - restarting backoff procedure')

                else:
                    log(self, 'Channel free')
                    # potencjalny blad bo moze czekac iles? co jakby usunac???????/
                    # with self.channel.tx_lock.request() as req:
                    #     yield req

                    log(self, f"Starting to wait backoff: ({self.back_off_time}) us...")
                    self.channel.back_off_list_NR.append(self)  # join the list off stations which are waiting Back Offs
                    self.waiting_backoff = True

                    yield self.env.timeout(self.back_off_time)  # join the environment action queue

                    log(self, f"Backoff waited, sending frame...")
                    self.back_off_time = -1  # leave the loop
                    self.waiting_backoff = False

                    self.channel.back_off_list_NR.remove(
                        self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                log(self, "Waiting was interrupted")
                # self.back_off_time -= (self.env.now - start)  # set the Back Off to the remaining one
                # odejmowac tylko pelne 9us sloty
                # if start == None:
                #     start = 0

                if self.first_interrupt and start is not None and self.waiting_backoff is True:
                    log(self, "Backoff was interrupted, waiting to resume backoff...")
                    already_waited = self.env.now - start

                    if already_waited <= prioritization_period_time:
                        self.back_off_time -= prioritization_period_time
                        log(self, f"Interrupted in PP time {prioritization_period_time}, backoff {self.back_off_time}")
                    else:
                        slots_waited = int(
                            (already_waited - prioritization_period_time) / self.config_nr.observation_slot_duration)
                        # self.back_off_time -= already_waited  # set the Back Off to the remaining one
                        self.back_off_time -= ((
                                                       slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time)
                        log(self,
                            f"Completed slots(9us) {slots_waited} = {(slots_waited * self.config_nr.observation_slot_duration)}  plus PP time {prioritization_period_time}")
                        log(self,
                            f"Backoff decresed by {(slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time} new Backoff {self.back_off_time}")

                    # log(self, f"already waited {already_waited} Backoff us, new Backoff {self.back_off_time}")
                    self.back_off_time += prioritization_period_time  # addnin new PP before next weiting
                    self.first_interrupt = False
                    self.waiting_backoff = False

                    # log(self, "Backoff was interrupted, waiting to resume backoff...")
                    # already_waited = self.env.now - start
                    #
                    # if already_waited <= prioritization_period_time:
                    #     self.back_off_time -= prioritization_period_time
                    #     log(self, "Interrupted in PP time")
                    # else:
                    #     self.back_off_time -= already_waited  # set the Back Off to the remaining one

                    # log(self, f"already waited {already_waited} Backoff us, new Backoff {self.back_off_time}")
                    # self.back_off_time += prioritization_period_time # addnin new PP before next weiting
                    # self.first_interrupt = False
                    # self.waiting_backoff = False

    def wait_back_off(self):
        # Wait random number of slots N x OBSERVATION_SLOT_DURATION us
        global start
        self.back_off_time = self.generate_new_back_off_time(self.failed_transmissions_in_row)
        m = self.config_nr.M
        prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration
        # self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure

        while self.back_off_time > -1:
            # m = self.config_nr.M
            # prioritization_period_time = self.config_nr.deter_period + m * self.config_nr.observation_slot_duration

            try:
                with self.channel.tx_lock.request() as req:  # waiting  for idle channel -- empty channel
                    yield req

                self.first_interrupt = True
                self.back_off_time += prioritization_period_time  # add Priritization Period time to bacoff procedure
                log(self, f"Starting to wait backoff (with PP): ({self.back_off_time}) us...")
                start = self.env.now  # store the current simulation time
                self.channel.back_off_list_NR.append(self)  # join the list off stations which are waiting Back Offs

                yield self.env.timeout(self.back_off_time)  # join the environment action queue

                log(self, f"Backoff waited, sending frame...")
                self.back_off_time = -1  # leave the loop

                self.channel.back_off_list_NR.remove(self)  # leave the waiting list as Backoff was waited successfully

            except simpy.Interrupt:  # handle the interruptions from transmitting stations
                log(self, "Backoff was interrupted, waiting to resume backoff...")
                if self.first_interrupt and start is not None:
                    already_waited = self.env.now - start

                    if already_waited <= prioritization_period_time:
                        self.back_off_time -= prioritization_period_time
                        log(self, f"Interrupted in PP time {prioritization_period_time}, backoff {self.back_off_time}")
                    else:
                        slots_waited = int(
                            (already_waited - prioritization_period_time) / self.config_nr.observation_slot_duration)
                        # self.back_off_time -= already_waited  # set the Back Off to the remaining one
                        self.back_off_time -= ((
                                                       slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time)
                        log(self,
                            f"Completed slots(9us) {slots_waited} = {(slots_waited * self.config_nr.observation_slot_duration)}  plus PP time {prioritization_period_time}")
                        log(self,
                            f"Backoff decresed by {(slots_waited * self.config_nr.observation_slot_duration) + prioritization_period_time} new Backoff {self.back_off_time}")

                    self.first_interrupt = False
                    self.waiting_backoff = False

                # log(self, "Waiting was interrupted, waiting to resume backoff...")
                # if self.first_interrupt and start is not None:
                #
                #     already_waited = self.env.now - start
                #     slots_waited = int(already_waited / 9)
                #     log(self, f"Bacoff time reduced by: {(self.env.now - start)}")
                #     self.back_off_time -= (slots_waited * 9)  # set the Back Off to the remaining one
                #     self.first_interrupt = False

                # log(self, "Waiting was interrupted, waiting to resume backoff...")
                # if self.first_interrupt and start is not None:
                #     already_waited = self.env.now - start
                #     slots_waited = already_waited / 9
                #
                #
                #     log(self, f"Bacoff time reduced by: {(self.env.now - start)}")
                #     self.back_off_time -= (self.env.now - (slots_waited * 9))  # set the Back Off to the remaining one
                #     self.first_interrupt = False
                #     self.waiting_backoff = False

                # log(self, "Backoff was interrupted, waiting to resume backoff...")
                # already_waited = self.env.now - start
                #
                # if already_waited <= prioritization_period_time:
                #     self.back_off_time -= prioritization_period_time
                #     log(self, "Interrupted in PP time")
                # else:
                #     self.back_off_time -= already_waited  # set the Back Off to the remaining one
                #
                # log(self, f"already waited {already_waited} Backoff us, new Backoff {self.back_off_time}")
                # self.first_interrupt = False
                # self.waiting_backoff = False

    def sync_slot_counter(self):
        # Process responsible for keeping the next sync slot boundry timestamp
        self.desync = random.randint(self.config_nr.min_sync_slot_desync, self.config_nr.max_sync_slot_desync)
        self.next_sync_slot_boundry = self.desync
        log(self, f"Selected random desync to {self.desync} us")
        yield self.env.timeout(self.desync)  # randomly desync tx starting points
        while True:
            self.next_sync_slot_boundry += self.config_nr.synchronization_slot_duration
            log(self, f"Next synch slot boundry is: {self.next_sync_slot_boundry}")
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
                # self.env.timeout(self.transmission_to_send.transmission_time)
                # return False

            with self.channel.tx_lock.request() as lock:  # this station has the longest frame so hold the lock
                yield lock
                # log(self, f'{self.channel.back_off_list_NR}')

                for station in self.channel.back_off_list:  # stop all station which are waiting backoff as channel is not idle
                    # if station.process is not None:
                    #     station.process.interrupt()
                    if station.process.is_alive:
                        station.process.interrupt()
                for gnb in self.channel.back_off_list_NR:  # stop all station which are waiting backoff as channel is not idle
                    # if gnb.process is not None:
                    #     gnb.process.interrupt()
                    if gnb.process.is_alive:
                        gnb.process.interrupt()

                log(self, f'Transmission will be for: {self.transmission_to_send.transmission_time} time')

                yield self.env.timeout(self.transmission_to_send.transmission_time)

                self.channel.back_off_list_NR.clear()  # channel idle, clear backoff waiting list
                was_sent = self.check_collision()  # check if collision occurred

                if was_sent:  # transmission successful
                    self.channel.airtime_control_NR[self.name] += self.transmission_to_send.rs_time
                    log(self, f"adding rs time to control data: {self.transmission_to_send.rs_time}")
                    self.channel.airtime_data_NR[self.name] += self.transmission_to_send.airtime
                    log(self, f"adding data airtime to data: {self.transmission_to_send.airtime}")
                    # yield self.env.timeout(self.times.get_ack_frame_time())  # wait ack
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
            # yield self.env.timeout(self.times.ack_timeout)  # simulate ack timeout after failed transmission
            return False

        except simpy.Interrupt:  # this station does not have the longest frame, waiting frame time
            yield self.env.timeout(self.transmission_to_send.transmission_time)

        was_sent = self.check_collision()
        return was_sent

    def check_collision(self):  # check if the collision occurred
        # if len(self.channel.tx_list_NR) > 1 or len(
        #         self.channel.tx_list) > 1:  # check if there was more then one station transmitting
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
        log(self, "There was a collision")
        self.transmission_to_send.number_of_retransmissions += 1
        self.channel.failed_transmissions_NR += 1
        self.failed_transmissions += 1
        self.failed_transmissions_in_row += 1
        log(self, self.channel.failed_transmissions_NR)
        if self.transmission_to_send.number_of_retransmissions > 7:
            # self.frame_to_send = self.generate_new_frame()
            # self.transmission_to_send = self.gen_new_transmission();
            self.failed_transmissions_in_row = 0

    def sent_completed(self):
        log(self, f"Successfully sent transmission")
        self.transmission_to_send.t_end = self.env.now
        self.transmission_to_send.t_to_send = (self.transmission_to_send.t_end - self.transmission_to_send.t_start)
        self.channel.succeeded_transmissions_NR += 1
        self.succeeded_transmissions += 1
        self.failed_transmissions_in_row = 0
        # self.channel.bytes_sent += self.frame_to_send.data_size
        # self.channel.airtime_data[self.name] += self.transmission_to_send.transmission_time
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
    config_nr = Config_NR()
    # config_wifi = Config()

    for i in range(1, number_of_stations + 1):
        Station(environment, "Station {}".format(i), channel, config)

    for i in range(1, number_of_gnb + 1):
        Gnb(environment, "Gnb {}".format(i), channel, config_nr)

    # environment.run(until=simulation_time * 1000000) 10^6 milisekundy
    environment.run(until=simulation_time * 1000000)

    if number_of_stations != 0:
        p_coll = "{:.4f}".format(
            channel.failed_transmissions / (channel.failed_transmissions + channel.succeeded_transmissions))
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

    # normalizedChannelOccupancyTime = channel.succeeded_transmissions * ()

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

    # with open("val/coex/check/coex_gap_be_newPcol.csv", mode='a', newline="") as result_file:
    #     result_adder = csv.writer(result_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    #
    #     # nodes = number_of_stations + number_of_gnb
    #
    #     result_adder.writerow(
    #         [seed, number_of_stations, number_of_gnb, normalized_channel_occupancy_time, normalized_channel_efficiency,
    #          p_coll,
    #          normalized_channel_occupancy_time_NR, normalized_channel_efficiency_NR, p_coll_NR,
    #          normalized_channel_occupancy_time_all, normalized_channel_efficiency_all])

    write_header = True
    if os.path.isfile(output_csv):
        write_header = False
    with open(output_csv, mode='a', newline="") as result_file:
        result_adder = csv.writer(result_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        if write_header:
            result_adder.writerow([
                "Seed,WiFi,Gnb,ChannelOccupancyWiFi,ChannelEfficiencyWiFi,PcolWifi,ChannelOccupancyNR,ChannelEfficiencyNR,PcolNR,ChannelOccupancyAll,ChannelEfficiencyAll"])

        result_adder.writerow(
            [seed, number_of_stations, number_of_gnb, normalized_channel_occupancy_time, normalized_channel_efficiency,
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
    def __init__(self, name: str, timers: FBETimers, offset=0):
        self.name = self.__str__() + name
        self.env = None
        self.succeeded_transmissions = 0
        self.failed_transmissions = 0
        self.failed_transmissions_in_row = 0
        self.channel = None
        self.timers = timers
        self.process = None
        self.transmission_process = None
        self.transmission_time = 15
        self.skip_next_cot = False
        self.air_time = 0
        self.offset = offset
        self.run_with_offset = self.offset > 0

    @abstractmethod
    def start(self):
        pass

    def set_environment(self, env):
        self.env = env
        self.env.process(self.start())

    def set_channel(self, channel):
        self.channel = channel

    def process_cca(self):
        init = self.env.now
        try:
            self.channel.cca_list_NR_FBE.append(self)
            log(self, 'Sensing if channel is idle')
            if len(self.channel.tx_list_NR_FBE) > 0:
                raise simpy.Interrupt("CCA interrupted!")
            yield self.env.timeout(self.timers.cca)
            self.skip_next_cot = False
            self.channel.cca_list_NR_FBE.remove(self)
        except simpy.Interrupt:
            end = self.env.now
            diff = end - init
            log(self, 'CCA interrupted, skipping next FFP')
            if diff == 0:
                yield self.env.timeout(self.timers.cca)
            else:
                yield self.env.timeout(diff)
            self.skip_next_cot = True
            self.channel.cca_list_NR_FBE.remove(self)

    def process_init_offset(self):
        if self.run_with_offset:
            yield self.env.timeout(self.offset)
        # Init cca process
        self.process = self.env.process(self.process_cca())
        yield self.process

    def check_collisions(self):
        lists_len_sum = self.get_transmitters_list_len_sum()
        if lists_len_sum > 1 or lists_len_sum == 0:
            self.sent_failed()
            return False
        self.sent_completed()
        return True

    def send_transmission(self):
        self.channel.tx_list_NR_FBE.append(self)
        with self.channel.tx_lock.request() as request_token:
            try:
                log(self, f"Starting transmission")
                request = yield request_token | self.env.timeout(0)
                if request_token not in request:
                    # log(self, f"Collision in channel")
                    for station in self.channel.tx_list_NR_FBE:
                        if station != self and station.process.is_alive:
                            station.process.interrupt()
                    raise simpy.Interrupt("Collision in channel")
                for station in self.channel.cca_list_NR_FBE:
                    if station.process.is_alive:
                        station.process.interrupt()
                now = self.env.now
                if self.channel.simulation_time - now < self.timers.cot:
                    self.sent_completed(True)
                yield self.env.timeout(self.timers.cot)
                if len(self.channel.tx_list_NR_FBE) > 1:
                    self.sent_failed()
                else:
                    self.sent_completed()
                self.channel.tx_list_NR_FBE.remove(self)

            except simpy.Interrupt:
                log(self, f"Collision in channel")
                yield self.env.timeout(self.timers.cot)
                self.channel.tx_list_NR_FBE.remove(self)
                self.sent_failed()

    def sent_failed(self):
        log(self, f"Transmission failed")
        event = Event(self.name, EventType.CHANNEL_COLLISION, self.env.now)
        self.channel.event_list.append(event)
        self.failed_transmissions += 1
        self.channel.failed_transmissions_NR_FBE += 1

    def fbe_skip_process(self):
        yield self.env.process(self.skip_cot())
        yield self.env.process(self.wait_until_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def fbe_transmission_process(self):
        self.transmission_process = self.env.process(self.send_transmission())
        yield self.transmission_process
        yield self.env.process(self.wait_until_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def sent_completed(self, interrupted_by_simulation_end=False):
        log(self, f"Successfully sent transmission")
        event = Event(self.name, EventType.SUCCESSFUL_TRANSMISSION, self.env.now)
        self.channel.event_list.append(event)
        if interrupted_by_simulation_end:
            self.air_time = self.succeeded_transmissions * self.timers.cot + self.channel.simulation_time - self.env.now
            self.succeeded_transmissions += 1
        else:
            self.succeeded_transmissions += 1
            self.air_time = self.succeeded_transmissions * self.timers.cot
        self.channel.succeeded_transmissions_NR_FBE += 1

    def get_transmitters_list_len_sum(self):
        return len(self.channel.tx_list) + len(self.channel.tx_list_NR) + len(self.channel.tx_list_NR_FBE)

    def wait_until_cca(self):
        yield self.env.timeout(self.timers.idle_period - self.timers.cca)

    def skip_cot(self):
        yield self.env.timeout(self.timers.cot)

    def __str__(self) -> str:
        return "(FBE) "


class StandardFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0):
        super().__init__(name, timers, offset)

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.skip_next_cot:
                yield self.env.process(self.fbe_skip_process())
            else:
                yield self.env.process(self.fbe_transmission_process())

    def __str__(self) -> str:
        return "(Standard FBE) "


def select_random_number(random_range, bottom_range=1):
    return random.randint(bottom_range, random_range)


class RandomMutingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0, max_frames_in_a_row=5, max_muted_periods=5):
        super().__init__(name, timers, offset)
        self.max_frames_in_a_row = max_frames_in_a_row
        self.max_muted_periods = max_muted_periods
        self.selected_number_of_frames_in_a_row = -1
        self.selected_number_of_muted_periods = 0

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.selected_number_of_frames_in_a_row == 0:
                self.selected_number_of_muted_periods = select_random_number(self.max_muted_periods)
                log(self,
                    f"Selecting number of muted periods. Selected number: {self.selected_number_of_muted_periods}")
                for i in range(0, self.selected_number_of_muted_periods):
                    log(self, f"Skipping frame... {i + 1}/{self.selected_number_of_muted_periods}")
                    yield self.env.process(self.fbe_skip_process())
                    self.selected_number_of_frames_in_a_row = -1

            if self.skip_next_cot:
                yield self.env.process(self.fbe_skip_process())
            else:
                if self.selected_number_of_frames_in_a_row == -1:
                    self.selected_number_of_frames_in_a_row = \
                        select_random_number(self.max_frames_in_a_row)
                    log(self,
                        f'Selecting number of frames which will be transmitted in the row. '
                        f'Selected number: {self.selected_number_of_frames_in_a_row} ')

                log(self, f'Continuous frames to go: {self.selected_number_of_frames_in_a_row}')
                yield self.env.process(self.fbe_transmission_process())

    def process_cca(self):
        self.process = self.env.process(super().process_cca())
        yield self.process
        if self.skip_next_cot:
            self.selected_number_of_frames_in_a_row = -1

    def sent_failed(self):
        super().sent_failed()
        self.selected_number_of_frames_in_a_row = -1

    def sent_completed(self, interrupted_by_simulation_end=False):
        self.selected_number_of_frames_in_a_row += -1
        super().sent_completed(interrupted_by_simulation_end)

    def __str__(self) -> str:
        return "(Random-muting FBE) "


class FloatingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0):
        super().__init__(name, timers, offset)
        self.number_of_slots = math.floor(timers.idle_period / timers.observation_slot_time) - 1
        self.pause_time_after_transmission = 0

    def wait_random_time_before_cca(self):
        time_to_wait = select_random_number(self.number_of_slots) * self.timers.observation_slot_time
        log(self, f'Selected backoff before CCA : {time_to_wait}')
        self.pause_time_after_transmission = self.timers.idle_period - time_to_wait - self.timers.cca
        yield self.env.timeout(time_to_wait)

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            yield self.env.process(self.fbe_transmission_process())

    def fbe_skip_process(self):
        yield self.env.timeout(self.timers.cot + self.pause_time_after_transmission)

    def fbe_transmission_process(self):
        yield self.env.process(self.backoff_process())
        if self.skip_next_cot:
            yield self.env.process(self.fbe_skip_process())
        else:
            self.transmission_process = self.env.process(self.send_transmission())
            yield self.transmission_process
            log(self, f'Waiting : {self.pause_time_after_transmission} before next FFP')
            yield self.env.timeout(self.pause_time_after_transmission)

    def backoff_process(self):
        yield self.env.process(self.wait_random_time_before_cca())
        self.process = self.env.process(self.process_cca())
        yield self.process

    def process_init_offset(self):
        if self.run_with_offset:
            yield self.env.timeout(self.offset)

    def __str__(self) -> str:
        return "(Floating FBE) "


class FixedMutingFBE(FBE):

    def __init__(self, name: str, timers: FBETimers, offset=0, max_number_of_muted_periods=1):
        super().__init__(name, timers, offset)
        self.muted_periods_to_go = 0
        self.max_number_of_muted_periods = max_number_of_muted_periods

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.skip_next_cot:
                yield self.env.process(self.fbe_skip_process())
            else:
                if self.muted_periods_to_go > 0:
                    log(self,
                        f'Waiting muted periods after successful transmission. Muted periods to go '
                        f'{self.muted_periods_to_go}')
                    if self.muted_periods_to_go == 1:
                        yield self.env.process(self.fbe_skip_process())
                    else:
                        yield self.env.process(self.fbe_skip_process_without_cca())
                    self.muted_periods_to_go += -1
                else:
                    yield self.env.process(self.fbe_transmission_process())

    def fbe_skip_process_without_cca(self):
        yield self.env.timeout(self.timers.ffp)

    def sent_completed(self, interrupted_by_simulation_end=False):
        super().sent_completed(interrupted_by_simulation_end)
        self.muted_periods_to_go = self.max_number_of_muted_periods

    def __str__(self) -> str:
        return "(Fixed-muting FBE) "


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
        self.drop_frame = False
        self.init_cca = True

    def start(self):
        yield self.env.process(self.process_init_offset())
        while True:
            if self.backoff_counter == 0:
                yield self.env.process(self.fbe_transmission_process())
            else:
                yield self.env.process(self.fbe_skip_process())
            if self.drop_frame:
                self.drop_frame = False
                self.select_backoff()

    def process_init_offset(self):
        if self.run_with_offset:
            yield self.env.timeout(self.offset)

        self.select_backoff()
        yield from self.process_cca()

    def process_cca(self):
        self.process = self.env.process(super().process_cca())
        yield self.process

        if self.skip_next_cot:
            self.interrupt_counter += 1
            log(self, f'Interrupt counter incremented. Actual value: {self.interrupt_counter}')

        if self.backoff_counter != 0:
            self.backoff_counter -= 1
            log(self, f'Backoff decremented. Actual value: {self.backoff_counter}')

    def sent_failed(self):
        super().sent_failed()
        if self.retransmission_counter < self.maximum_number_of_retransmissions:
            self.retransmission_counter += 1
            log(self, f'Incrementing retransmission_counter to {self.retransmission_counter}')
            self.select_backoff()
        else:
            # In our case simply setting counter to 0 and restarting procedure in next ffp
            log(self,
                f'Retransmission_counter exceeded maximum number of retransmissions'
                f' {self.retransmission_counter}/{self.maximum_number_of_retransmissions}.'
                f'Dropping frame...')
            self.retransmission_counter = 0
            self.interrupt_counter = 0
            self.drop_frame = True
            self.select_backoff()

    def sent_completed(self, interrupted_by_simulation_end=False):
        super().sent_completed(interrupted_by_simulation_end)
        self.retransmission_counter = 0
        self.select_backoff()

    def select_backoff(self):
        modulo = self.retransmission_counter % self.maximum_number_of_retransmissions
        if modulo < self.threshold:
            self.backoff_counter = self.init_backoff_value + self.interrupt_counter
            self.interrupt_counter = 0
        else:
            log(self, f'False in r%m < threshold ({modulo}<{self.threshold})')
            top_range = self.maximum_number_of_retransmissions - 1
            self.backoff_counter = select_random_number(top_range, bottom_range=0)
        log(self, f'Selected new backoff counter: {self.backoff_counter}')

    def __str__(self) -> str:
        return "(Deterministic-backoff FBE) "


def get_fbe_versions():
    return [FBEVersion.STANDARD_FBE, FBEVersion.FLOATING_FBE, FBEVersion.FIXED_MUTING_FBE, FBEVersion.RANDOM_MUTING_FBE,
            FBEVersion.DETERMINISTIC_BACKOFF_FBE]


class FBEVersion(Enum):
    STANDARD_FBE = 1
    RANDOM_MUTING_FBE = 2
    FIXED_MUTING_FBE = 3
    FLOATING_FBE = 4
    DETERMINISTIC_BACKOFF_FBE = 5


# class GnbFBE:
#     station_number = 0
#
#     def __init__(self,
#                  name: str,
#                  env: simpy.Environment,
#                  channel: dataclass,
#                  col: str,
#                  timers: FBETimers,
#                  run_with_offset=False,
#                  offset=0,
#                  fbe_enchantment='none'
#                  ):
#         self.name = name
#         self.env = env
#         self.succeeded_transmissions = 0
#         self.failed_transmissions = 0
#         self.failed_transmissions_in_row = 0
#         self.channel = channel
#         self.col = col
#         self.timers = timers
#         self.process = None
#         self.transmission_process = None
#         self.transmission_time = 15
#         self.skip_next_cot = False
#         self.air_time = 0
#         self.run_with_offset = run_with_offset
#         self.offset = offset
#         if fbe_enchantment not in fbe_enchantments:
#             print(f'Enchantment: {fbe_enchantment} '
#                   f'in {fbe_enchantments} creating GnbFBE object with standard functionality')
#             fbe_enchantment = 'none'
#         self.fbe_enchantment = fbe_enchantment
#         self.max_frames_in_a_row = 5
#         self.max_muted_periods = 5
#         self.selected_number_of_frames_in_a_row = -1
#         self.selected_number_of_muted_periods = 0
#
#         env.process(self.start())
#
#     def start(self):
#         if self.run_with_offset:
#             yield self.env.timeout(self.offset)
#         # Init cca process
#         self.process = self.env.process(self.process_cca())
#         yield self.process
#
#         if self.fbe_enchantment == 'none':
#             yield self.env.process(self.standard_fbe())
#         elif self.fbe_enchantment == 'continuous_frames':
#             yield self.env.process(self.continuous_frames_enchantment())
#
#     def continuous_frames_enchantment(self):
#         while True:
#             if self.selected_number_of_frames_in_a_row == 0:
#                 self.selected_number_of_muted_periods = self.gen_random_station_start_shift(self.max_muted_periods)
#                 log(self,
#                     f"Selecting number of muted periods. Selected number: {self.selected_number_of_muted_periods}")
#                 for i in range(0, self.selected_number_of_muted_periods):
#                     log(self, f"Skipping frame... {i + 1}/{self.selected_number_of_muted_periods}")
#                     yield self.env.process(self.fbe_skip_process())
#                     self.selected_number_of_frames_in_a_row = -1
#
#             if self.skip_next_cot:
#                 yield self.env.process(self.fbe_skip_process())
#             else:
#                 if self.selected_number_of_frames_in_a_row == -1:
#                     self.selected_number_of_frames_in_a_row = \
#                         self.gen_random_station_start_shift(self.max_frames_in_a_row)
#                     log(self,
#                         f'Selecting number of frames which will be transmitted in the row. '
#                         f'Selected number: {self.selected_number_of_frames_in_a_row} ')
#
#                 log(self, f'Continuous frames to go: {self.selected_number_of_frames_in_a_row}')
#                 yield self.env.process(self.fbe_transmission_process())
#
#     def standard_fbe(self):
#         while True:
#             if self.skip_next_cot:
#                 yield self.env.process(self.fbe_skip_process())
#             else:
#                 yield self.env.process(self.fbe_transmission_process())
#
#     def fbe_skip_process(self):
#         yield self.env.process(self.skip_cot())
#         yield self.env.process(self.wait_until_cca())
#         self.process = self.env.process(self.process_cca())
#         yield self.process
#
#     def fbe_transmission_process(self):
#         self.transmission_process = self.env.process(self.send_transmission())
#         yield self.transmission_process
#         yield self.env.process(self.wait_until_cca())
#         self.process = self.env.process(self.process_cca())
#         yield self.process
#
#     def wait_until_cca(self):
#         yield self.env.timeout(self.timers.idle_period - self.timers.cca)
#
#     def skip_cot(self):
#         yield self.env.timeout(self.timers.cot)
#
#     def gen_random_station_start_shift(self, random_range):
#         return random.randint(1, random_range)
#
#     def process_cca(self):
#         init = self.env.now
#         try:
#             self.channel.cca_list_NR_FBE.append(self)
#             log(self, 'Sensing if channel is idle')
#             if len(self.channel.tx_list_NR_FBE) > 0:
#                 raise simpy.Interrupt("CCA interrupted!")
#             yield self.env.timeout(self.timers.cca)
#             self.skip_next_cot = False
#             self.channel.cca_list_NR_FBE.remove(self)
#         except simpy.Interrupt:
#             end = self.env.now
#             diff = end - init
#             log(self, 'CCA interrupted, skipping next FFP')
#             if diff == 0:
#                 yield self.env.timeout(self.timers.cca)
#             else:
#                 yield self.env.timeout(diff)
#             self.skip_next_cot = True
#             if self.fbe_enchantment == CONTINUOUS_FRAMES_ENCHANTMENT:
#                 self.selected_number_of_frames_in_a_row = -1
#             self.channel.cca_list_NR_FBE.remove(self)
#
#     def check_collision(self):
#         lists_len_sum = self.get_transmitters_list_len_sum()
#         if lists_len_sum > 1 or lists_len_sum == 0:
#             self.sent_failed()
#             return False
#         self.sent_completed()
#         return True
#
#     def send_transmission(self):
#         self.channel.tx_list_NR_FBE.append(self)
#         with self.channel.tx_lock.request() as request_token:
#             try:
#                 log(self, f"Starting transmission")
#                 request = yield request_token | self.env.timeout(0)
#                 if request_token not in request:
#                     raise simpy.Interrupt("Collision in channel")
#                 for station in self.channel.cca_list_NR_FBE:
#                     if station.process.is_alive:
#                         station.process.interrupt()
#                 now = self.env.now
#                 if 1000000 - now < self.timers.cot:
#                     self.sent_completed(True)
#                 yield self.env.timeout(self.timers.cot)
#                 if len(self.channel.tx_list_NR_FBE) > 1:
#                     self.sent_failed()
#                 else:
#                     self.sent_completed()
#                 self.channel.tx_list_NR_FBE.remove(self)
#
#             except simpy.Interrupt:
#                 yield self.env.timeout(self.timers.cot)
#                 self.channel.tx_list_NR_FBE.remove(self)
#                 self.sent_failed()
#
#     def get_transmitters_list_len_sum(self):
#         return len(self.channel.tx_list) + len(self.channel.tx_list_NR) + len(self.channel.tx_list_NR_FBE)
#
#     def sent_failed(self):
#         log(self, f"Transmission failed")
#         self.failed_transmissions += 1
#         self.channel.failed_transmissions_NR_FBE += 1
#         if self.fbe_enchantment == CONTINUOUS_FRAMES_ENCHANTMENT:
#             self.selected_number_of_frames_in_a_row = -1
#
#     def sent_completed(self, interrupted_by_simulation_end=False):
#         log(self, f"Successfully sent transmission")
#         if self.fbe_enchantment == CONTINUOUS_FRAMES_ENCHANTMENT:
#             self.selected_number_of_frames_in_a_row += -1
#         if interrupted_by_simulation_end:
#             self.air_time = self.succeeded_transmissions * self.timers.cot + 1000000 - self.env.now
#             self.succeeded_transmissions += 1
#         else:
#             self.succeeded_transmissions += 1
#             self.air_time = self.succeeded_transmissions * self.timers.cot
#         self.channel.succeeded_transmissions_NR_FBE += 1
class EventType(Enum):
    SUCCESSFUL_TRANSMISSION = 1
    CHANNEL_COLLISION = 2


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
    event_list: List[Event] = field(default_factory=list)
    # problem list of station objects, what if we 2 differenet station objects???

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
    test = ['aa', 'bb', 'cc']
    test2 = ['aaa', 'bbb', 'ccc']
    test3 = (test, test2)
    for x, y in test, test2:
        print(x + '\t' + y)

#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Sat Sep 16 16:16:02 2023

@author: Zhao Kuangshi
'''
import time
import socket
import argparse
import numpy as np
from enum import Enum
from struct import unpack
from typing import List, Tuple
from threading import Lock, Thread

def resolveData(raw: bytes) -> dict:
    """
    解析HEEG数据的实用函数，接受传入一段合法的packet数据，返回解析该段数据的结果字典。

    > **注意：**
    > 本函数不处理断包、粘包等TCP协议相关的事务，对于数据包的拆分和验证应当在外层执行。

    参数
    ----
    raw : bytes
        一个合法的HEEG packet。二进制串类型。

    返回
    ----
    dict
        解析HEEG packet的结果字典。
        其中：
        timeStamp: int        当前包的时间戳，单位为ms
        channelCount: int     通道数
        sampleRate: int       采样率
        datas: np.ndarray     数据，形状为当前packet的 (通道数, 样本点数)
        trigger: int | None   trigger信号，仅解析来自串口的信号。当存在trigger时为
                              trigger的值，当不存在trigger时为None
    """
    try:
        ###### 对packet的头部解包 #####
        # 获取头部长度
        headerLength = int.from_bytes(raw[2:6], byteorder="little",
                                    signed=False)
        # 截取头部
        head: bytes = raw[:headerLength]
        # 解包
        # 解包结果从左至右依次为：包头标识符、头部长度、整包长度、当前包的时间戳、采
        # 样率、当前包（每通道）含有的样本点数
        (_, headerLength, totalLength, timeStamp, channelCount, sampleRate,
            dataCountPerChannel) = unpack("<H6I", head)

        ###### 解析数据 ######
        # 数据二进制串是一个展平的二维数组，外层维度（第0维）代表通道，而内层维度（第
        # 1维）代表样本点

        # 从packet中截取数据的二进制串，每一个样本点都占用4个bytes，总样本点数等于
        # 每个通道的样本点数乘以通道数
        bDatas: bytes = raw[
            headerLength:headerLength+dataCountPerChannel*channelCount*4]
        # 对二进制串进行解包
        datas: np.ndarray = np.array(
            unpack(f"<{dataCountPerChannel*channelCount}f", bDatas)).reshape(
                channelCount, dataCountPerChannel
            )
        
        # 从packet中截取trigger的二进制串，trigger占用30个byte的空间
        bTrigger: bytes = raw[
            headerLength+dataCountPerChannel*channelCount*4:\
            headerLength+dataCountPerChannel*channelCount*4+30]
        # 解析trigger字符串，使用utf8解码，并去除空白的占位符
        trigger: str = unpack("<30s", bTrigger)[0].decode("utf8").strip("\x00")
        if trigger != "":  # 存在trigger的话
            try:
                # 如果trigger来自于串口，它将符合%s:%d的协议，从中取出实际的值
                trigger = int(trigger.split(":")[1])
            except:
                # 如果trigger来自其它设备，暂不支持
                trigger = None
        else:  # 不存在trigger的话
            trigger = None
        # 拼装返回结果
        rst: dict = {
            "timeStamp": timeStamp,
            "channelCount": channelCount,
            "sampleRate": sampleRate,
            "dataCountPerChannel": dataCountPerChannel,
            "datas": datas,
            "trigger": trigger
        }
    except Exception as e:
        # 当发生错误时，大概率是因为传入本函数的二进制串存在问题，如发生脏包、错包、
        # 粘包等，将输出函数实际收到的二进制流以待分析原因
        print(f"Received bytes: \n{raw.hex()}")
        raise e
    return rst

class NeusenHEEGThread:
    def __init__(self, isCsvOutput):
        """初始化HEEG接收端"""
        self.state = state.NOTCONNECT
        self.socketBuffer: bytes = bytes()
        self.sockBufLock: Lock = Lock()

        self.isCsvOutput = isCsvOutput
        self.csvFD = None
        self.topChannelCount = 8

    def isEnableCsvOutput(self):
        return self.isCsvOutput

    def openOutput(self):    
        if self.isEnableCsvOutput():
            filename = "heeg_sample.csv"
            self.csvFD = open(filename, 'w')
            for i in range(self.topChannelCount):
               self.csvFD.write("channel_{},".format(i+1))
            self.csvFD.write("\n")

    def closeOutput(self):
        if self.isEnableCsvOutput():
            self.csvFD.close()

    def connect(self, hostname: str = '127.0.0.1', port: int = 8172):
        """
        连接指定地址的转发服务，默认为127.0.0.1:8172
        若返回值为True，代表连接失败；反之为连接成功。

        连接成功后，会自动开始接收数据。记得调用`stop()`方法结束接收数据。
        """
        self.hostname: str = hostname
        self.port: int = port
        # 建立连接
        self.sock: socket.socket = socket.socket(socket.AF_INET,
                                                 socket.SOCK_STREAM)
        reconnecttime = 0
        while self.state == state.NOTCONNECT:
            try:
                self.sock.connect((self.hostname, self.port))
                self.sock.setblocking(False)
                self.state = state.CONNECTED
                self.openStream()
            except:
                reconnecttime += 1
                print(f'connection failed, retrying for {reconnecttime} times')
                time.sleep(1)
                if reconnecttime > 2:
                    break
        return self.state == state.NOTCONNECT

    def read_thread(self):
        self.openOutput()
    
        if self.state == state.NOTCONNECT:
            raise RuntimeError("Cannot start receiving data before connect.")
        while self.state != state.ABORT:
            self.recv()
            time.sleep(1e-6)

        self.closeOutput()

    def recv(self):
        buf: bytes = bytes()
        retry: bool = True
        while retry:
            try:
                for i in range(10):
                    buf += self.sock.recv(4096)
                    if len(self.socketBuffer) > 0:
                        self.resolve()
            except:
                if len(buf) > 0:
                    retry = False
                else:
                    retry = True
        self.sockBufLock.acquire()
        self.socketBuffer += buf
        self.sockBufLock.release()
        self.resolve()

    def openStream(self):
        Thread(target=self.read_thread).start()

    def isReady(self):
        return self.state == state.READY

    def start(self):
        if self.state == state.NOTCONNECT or (self.state == state.CONNECTED):
            raise RuntimeError("Cannot start data recording before ready.")
        elif self.state == state.READY:
            self.state = state.RUNNING

    def resolve(self):
        # ===================== lock =====================
        while True:
            try:
                self.sockBufLock.acquire()
                isMeta: bool = False
                if len(self.socketBuffer) < 2:  # empty buffer
                    return
                # 1. check head token
                dataHeadToken: bytes = bytes.fromhex('5AA5')  # expected head
                headToken: bytes = self.socketBuffer[0:2]  # real head
                if headToken != dataHeadToken:
                    raise ValueError(
                        f"Invalid head token \"{headToken.hex()}\"")
                # 2. get the whole msg according to head
                totalLength : int = int.from_bytes(
                    self.socketBuffer[6:10], byteorder="little", signed=False)
                msg: bytes = self.socketBuffer[:totalLength]
                if totalLength != len(msg):  # insufficient buffer
                    return
                # 3. check tail token
                dataTailToken: bytes = bytes.fromhex('A55A')  # expected tail
                tailToken: bytes = msg[-2:]
                if tailToken != dataTailToken:
                    raise ValueError(
                        f"Invalid tail token \"{tailToken.hex()}\"")
                # pop the msg from buffer
                self.socketBuffer = self.socketBuffer[totalLength:]
            finally:
                self.sockBufLock.release()
            # ===================== //lock =====================
            # treat data packet
            if self.state == state.CONNECTED:  # stabilized
                self.state = state.READY
            dataStuct: dict = resolveData(msg)  # not data array
            dataArr = dataStuct["datas"]

            # csv
            if self.isEnableCsvOutput():    
                if self.topChannelCount > dataStuct["channelCount"]:
                   self.topChannelCount = dataStuct["channelCount"]

                for i in range(dataStuct["dataCountPerChannel"]):
                    for j in range(self.topChannelCount):
                        self.csvFD.write("{},".format(dataArr[j][i]))
                    self.csvFD.write("\n")
            else:
                print(dataArr)

    def stop(self):
        self.state = state.ABORT

class state(Enum):
    NOTCONNECT = 0  # the first state with nothing ready
    CONNECTED  = 1  # already connect the data server, demonstrating at least
                    # there is a available TCP port
    READY      = 2  # successfully receive and resolve the META packet, and
                    # open the data flow in order to stabilize it. (data will
                    # not e stored into buffer)
    RUNNING    = 3  # receiving data at present
    ABORT      = 4

### 用例及demo  ###
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process args.')
    parser.add_argument('-o', '--outputCsv', action='store_true', help='output top 8 channel sample to csv')
    args = parser.parse_args()

    heeg = NeusenHEEGThread(args.outputCsv)
    heeg.connect()
    time.sleep(10)
    heeg.stop()

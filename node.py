# -*- coding: utf-8 -*-
"""
@author: yuan_xin
@contact: yuanxin9997@qq.com
@file: node.py
@time: 2020/10/19 17:24
@description:
"""


class Node(object):
    '''
    顾客点类：
    c_id:Number,顾客点编号（任务点编号）（TaskNo）
    x:Number,点的横坐标
    y:Number,点的纵坐标
    demand:Number,点的需求量
    ready_time:Number,点的最早访问时间
    due_time:Number,点的最晚访问时间
    service_time:Number,点的服务时间
    pickup_index:Number,点如果是取货任务，那么此值等于0；点如果是送货任务，那么此值对应其取货任务的点编号
    delivery_index:Number,点如果是送货任务，那么此值等于0；点如果是取货任务，那么此值对应其送货任务的点编号
    belong_veh:所属车辆编号
    '''

    def __init__(self, c_id, demand, ready_time, due_time, service_time, pickup_index, delivery_index, block_id,
                 container_id):
        self.c_id = c_id
        self.demand = demand
        self.ready_time = ready_time
        self.due_time = due_time
        self.service_time = service_time
        self.pickup_index = pickup_index
        self.delivery_index = delivery_index
        self.block_id = block_id
        self.container_id = container_id
        self.belong_veh = None


class PDNode(object):
    """一对取送货点类（PD-pair）"""

    def __init__(self, pd_id, p_id, d_id, travel_distance, travel_time, p_tw, d_tw, p_service_time, d_service_time,
                 container_id, p_block_id, d_block_id):
        self.pd_id = pd_id  # PD点对的ID，与读取数据中的Request的键相同，从0开始编号
        self.p_id = p_id  # PD点对中P点的TaskNo
        self.d_id = d_id  # PD点对中D点的TaskNo
        self.p_time_window = p_tw  # PD点对中P点的时间窗
        self.d_time_window = d_tw  # PD点对中D点的时间窗
        self.p_service_time = p_service_time  # PD点对中P点的服务时间
        self.d_service_time = d_service_time  # PD点对中D点的服务时间
        self.p_block_id = p_block_id  # PD点对中P点的箱区ID
        self.d_block_id = d_block_id  # PD点对中D点的箱区ID

        self.container_id = container_id  # PD点对共同服务的中转箱的ID
        self.travel_distance = travel_distance  # 车辆从P点到D点的行驶距离
        self.travel_time = travel_time  # 车辆从P点到D点的行驶时间
        self.time_window_period = d_tw[1] - p_tw[0]  # 该PD点对的任务时间窗
        self.belong_veh = None  # 访问PD点对的车辆的ID

    def check_feasible(self):  # 检查PD-pair是否可行或有效
        if self.p_time_window[0] >= self.d_time_window[1]:  # 如果P的左时间窗比D的右时间窗晚
            return "error1"
        # P的左时间窗+P的服务时间+PD行驶时间+D的服务时间 比D的右时间窗晚，那么该PD对是无效的
        if self.travel_time + self.p_service_time + self.d_service_time >= self.time_window_period:
            return "error2"

    def __str__(self):  # 重载print()
        # __str__方法,返回对象的描述信息，print函数输出时使用
        description = "PD点对[%s,%s]无效，其时间窗分别为%s,%s,行驶距离为%s，行驶时间为%s" % \
                      (self.p_id, self.d_id, self.p_time_window, self.d_time_window, self.travel_distance,
                       self.travel_time)
        return description
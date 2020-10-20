# -*- coding: utf-8 -*-
"""
@author: yuan_xin
@contact: yuanxin9997@qq.com
@file: vehicle.py
@time: 2020/10/19 17:24
@description:
"""
from collections import Iterable

flat = lambda t: [x for sub in t for x in flat(sub)] if isinstance(t, Iterable) else [t]


class Vehicle(object):
    '''
    车辆类：
    v_id:Number,车辆编号
    cap:Number,车的最大载重量
    speed:Number，车辆的行驶速度

    load:Number,车的载重量
    distance:Number,车的行驶距离
    violate_time:Number,车违反其经过的各点时间窗时长总和
    route:List,车经过的点index的列表
    start_time:List,车在每个点的开始服务时间
    '''

    def __init__(self, v_id, cap, speed, distance_matrix, nodes):
        self.v_id = v_id
        self.cap = cap
        self.speed = speed

        self.load = 0
        self.distance = 0

        self.route = [0]  # 车辆第一个服务的点默认为开始depot
        self.pd_route = [0]  # 以列表的形式插入PD点对

        self.nodes = nodes  # 不是以pd点对，而是以单个客户生成的Node类对象

        self.total_hard_violate_time = 0  # 总的违背的硬时间窗，取货点P左右时间窗均为硬时间窗，送货点D的左时间窗为硬时间窗
        self.total_soft_violate_time = 0  # 总的违背的软时间窗，送货点D的有时间窗为软时间窗
        self.start_time = {0: 0}  # 开始服务每个节点的时间
        self.wait_time = {0: 0}  # 在每个节点上的等待时间
        # self.violate_time = [0] # 在每个节点上的时间窗违背

        self.distance_matrix = distance_matrix  # 为了简便，将距离矩阵传进来，并且在方法内部计算时间矩阵
        self.time_matrix = {}  # 通过类方法进行计算

    # 根据距离矩阵和车辆的速度计算车辆自己的时间矩阵
    def cal_time_matrix(self):
        for (i, j) in self.distance_matrix.keys():
            self.time_matrix[i, j] = self.distance_matrix[i, j] / self.speed

    # 将PD点对插入到车辆的路径当中，每一PD对以列表的形式插入
    def insert_pd_node(self, p_id, d_id, index=0):
        if index == 0:
            # self.route.append(p_id)  # 如果index=0，那么将pd点对依次插入到车经过的点的后面
            # self.route.append(d_id)
            self.pd_route.append([p_id, d_id])  # 将pd点对以列表的形式插入到pd_route中
            self.route = flat(self.pd_route)  # 再将pd_route中的嵌套列表展平
        else:  # 如果索引index不等于0
            # self.route.insert(index,d_id)
            # self.route.insert(index,p_id)
            self.pd_route.insert(index, [p_id, d_id])
            self.route = flat(self.pd_route)  # 再将pd_route中的嵌套列表展平
        # node.belong_veh = self.v_id
        self.update_info(self.nodes)  # 类方法，参见下方，用来更新类对象veh的载量、距离、开始服务时间、时间窗违反

    # 将结束depot插入到车辆的路径当中
    def insert_end_depot(self, end_depot_id):
        self.pd_route.append(end_depot_id)
        self.route = flat(self.pd_route)  # 再将pd_route中的嵌套列表展平
        self.update_info(self.nodes)

    # 根据车辆路径中的索引删除节点
    def del_node_by_index(self, index):
        self.pd_route.pop(index)
        self.route = flat(self.pd_route)  # 再将pd_route中的嵌套列表展平
        self.update_info(self.nodes)

    # 将PDNode类对象pd_node，从车辆路径当中删除
    def del_node_by_node(self, pd_node):
        self.pd_route.remove([pd_node.p_id, pd_node.d_id])
        self.route = flat(self.pd_route)  # 再将pd_route中的嵌套列表展平
        self.update_info(self.nodes)

    # 检查当前车辆的路径是否可行
    def check_vehicle_route_feasible(self):
        # 如果违背硬时间窗，那么不可行
        if self.total_hard_violate_time == 0:
            fesible_status = 1
        else:
            fesible_status = 0
        return fesible_status

    # 更新载重、距离、开始服务时间、时间窗违反
    def update_info(self, nodes):

        # 更新载重，不用考虑载量，只要按depot，PD，PD，...的顺序访问所有的点，就不用考虑载量
        '''
        cur_load = 0
        for n in self.route:
            cur_load += nodes[n].demand
        self.load = cur_load
        '''

        # 更新距离
        cur_distance = 0
        for i in range(len(self.route) - 1):  # 比如route=[0,1,2,3,4,5]
            cur_distance += self.distance_matrix[self.route[i], self.route[i + 1]]
        self.distance = cur_distance

        # 更新开始服务时间、等待时间、违背时间
        # 取货点P的左右时间窗是硬时间窗，送货点D的左时间窗是硬时间窗，右时间窗是软时间窗，可以违背但有惩罚成本
        # 早到等待
        self.start_time = {0: 0}  # 开始depot的开始服务时间，默认从0开始
        self.wait_time = {0: 0}  # 开始depot的等待时间，默认为0
        arrival_time = 0
        cur_total_hard_violate_time = 0
        cur_total_soft_violate_time = 0

        for i in range(1, len(self.route) - 1):  # route=[0,p,d,p,d,...,p,d,2*len(container)+1]

            # 传入的notes为按每个任务创建的Node类对象，其顺序依次为[0,p1,d1,p2,d2,...,pn,dn,2*len(container)+1]

            # 到达节点i的时间 = 上一个节点i-1的开始服务时间 + 上一个节点i-1的服务时间 + 节点i-1到节点i的车辆行驶时间
            arrival_time += self.start_time[self.route[i - 1]] + nodes[self.route[i - 1]].service_time + \
                            self.time_matrix[self.route[i - 1], self.route[i]]

            # 以下的i为取货点P，时间窗为硬时间窗，早到等待，不可晚到，如果晚到，则返回 infeasible
            if nodes[self.route[i]].pickup_index == 0 and nodes[self.route[i]].delivery_index != 0:

                if arrival_time <= nodes[self.route[i]].ready_time:  # 早于P点的左时间窗
                    self.start_time[self.route[i]] = nodes[self.route[i]].ready_time
                    self.wait_time[self.route[i]] = nodes[self.route[i]].ready_time - arrival_time

                elif arrival_time >= nodes[self.route[i]].due_time:  # 晚于P点的右时间窗
                    self.start_time[self.route[i]] = arrival_time - nodes[self.route[i]].service_time  # 相当于不服务该节点
                    self.wait_time[self.route[i]] = 0
                    cur_total_hard_violate_time += arrival_time + nodes[self.route[i]].service_time - nodes[
                        self.route[i]].due_time

                elif nodes[self.route[i]].ready_time < arrival_time and arrival_time < nodes[
                    self.route[i]].due_time:  # 在P的左右时间窗内到达

                    if arrival_time + nodes[self.route[i]].service_time > nodes[self.route[i]].due_time:  # 如果来不及全部服务完
                        self.start_time[self.route[i]] = arrival_time
                        self.wait_time[self.route[i]] = 0
                        cur_total_hard_violate_time += arrival_time + nodes[self.route[i]].service_time - nodes[
                            self.route[i]].due_time

                    else:
                        self.start_time[self.route[i]] = arrival_time
                        self.wait_time[self.route[i]] = 0

            # 以下i为送货点D，左时间窗为硬时间窗，早到等待，右时间窗为软时间窗
            if nodes[self.route[i]].pickup_index != 0 and nodes[self.route[i]].delivery_index == 0:

                if arrival_time <= nodes[self.route[i]].ready_time:  # 早于D点的左时间窗
                    self.start_time[self.route[i]] = nodes[self.route[i]].ready_time
                    self.wait_time[self.route[i]] = nodes[self.route[i]].ready_time - arrival_time

                elif arrival_time + nodes[self.route[i]].service_time <= nodes[self.route[i]].due_time:  # 来得及服务
                    self.start_time[self.route[i]] = arrival_time
                    self.wait_time[self.route[i]] = 0

                elif arrival_time + nodes[self.route[i]].service_time >= nodes[self.route[i]].due_time:  # 来不及服务
                    self.start_time[self.route[i]] = arrival_time
                    self.wait_time[self.route[i]] = 0
                    cur_total_soft_violate_time += arrival_time + nodes[self.route[i]].service_time - nodes[
                        self.route[i]].due_time

        # 计算结束depot的开始服务时间和等待时间（结束depot没有惩罚成本）
        self.start_time[self.route[-1]] = self.start_time[self.route[-2]] + nodes[self.route[-2]].service_time + \
                                          self.time_matrix[self.route[-2], self.route[-1]]
        self.wait_time[self.route[-1]] = 0  # 在结束depot上，等待时间为0

        # 更新总的违背的软硬时间窗
        self.total_hard_violate_time = cur_total_hard_violate_time
        self.total_soft_violate_time = cur_total_soft_violate_time

    def __str__(self):  # 重载print()
        description = "车辆%s的信息:\n" \
                      "总行驶距离：%s \n" \
                      "总违背的软时间窗：%s \n" \
                      "总违背的硬时间窗：%s \n" \
                      "路径：%s \n" \
                      "开始服务时间：%s \n" \
                      "等待时间：%s" % (self.v_id, self.distance, self.total_soft_violate_time, self.total_hard_violate_time,
                                   self.pd_route, self.start_time, self.wait_time)
        return description
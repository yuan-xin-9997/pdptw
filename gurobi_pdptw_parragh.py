# -*- coding: utf-8 -*-
"""
@author: yuan_xin
@contact: yuanxin9997@qq.com
@file: gurobi_pdptw_parragh.py
@time: 2020/10/20 11:13
@description:使用Python调用Gurobi求解PDPTW问题；Gurobi是标杆，用来对比其他算法用的.
==求解器：Gurobi 9.0.3
==模型：Parragh, S. N., et al. (2008). "A survey on pickup and delivery problems: Part II: Transportation between pickup
and delivery locations." Journal für Betriebswirtschaft 58(2): 81-117.
==Benchmark：Li & Lim's PDPTW benchmark - SINTEF Applied Mathematics
"""

from gurobipy import *
from gurobipy import GRB
import pandas as pd
import math
import time


def read_pdptw_benchmark_data(path):
    """读取Benchmark数据"""

    # 读取车辆信息
    vehicles_info = pd.read_table(path, nrows=1, names=['K', 'C', 'S'])
    vehicles = {}
    for i in range(vehicles_info.iloc[0, 0]):
        vehicles[i] = [vehicles_info.iloc[0, 1], vehicles_info.iloc[0, 2]]  # 键i=车辆的序号，值为[车辆容量、速度]

    # 读取Depot和运输任务信息
    column_names = ['TaskNo', 'X', 'Y', 'Demand', 'ET', 'LT', 'ST', 'PI', 'DI']
    task_info = pd.read_table(path, skiprows=[0], names=column_names)
    
    node_num = task_info.shape[0]
    
    # 获取任务号
    task_no_list = []
    for i in range(node_num):
        task_no_list.append(task_info.iloc[i, 0])
    
    # 提取Depot和取送货点（Customer）的位置坐标Location
    locations = {}
    for i in range(node_num):
        locations[task_info.iloc[i, 0]] = [task_info.iloc[i, 1], task_info.iloc[i, 2]]  # 键为depot或客户编号，值为相应的坐标（x，y）

    # 提取Depot和取送货点（Customer）的需求Demand
    demand = {}
    for i in range(node_num):
        demand[task_info.iloc[i, 0]] = task_info.iloc[i, 3]
    # print('Demand',Demand)

    # 提取Depot和取送货点（Customer）的时间窗Time Windows
    time_window = {}
    earliest_time = task_info.sort_values(by='ET').iloc[0, 4]
    latest_time = task_info.sort_values(by='LT', ascending=False).iloc[0, 5]
    for i in range(node_num):
        time_window[task_info.iloc[i, 0]] = [task_info.iloc[i, 4], task_info.iloc[i, 5]]

    # 提取Depot和取送货点（Customer）的服务时间 ServiceTime
    service_time = {}
    for i in range(node_num):
        service_time[task_info.iloc[i, 0]] = task_info.iloc[i, 6]

    # 提取运输Request
    # 对于取货任务，PICKUP索引为0，而同一行的DELIVERY索引给出相应送货任务的索引
    request = {}
    count = 0  # 记录运输需求的数量
    for i in range(1, node_num-1):
        if task_info.iloc[i, 7] == 0:
            request[count] = [task_info.iloc[i, 0], task_info.iloc[i, 8]]  # 将取送货点组合在一起，键为count，值为[取货点，送货点]
            count += 1

    return vehicles, locations, demand, time_window, service_time, request, earliest_time, latest_time, task_no_list


def calculate_euclid_distance(x1, y1, x2, y2):
    """计算Euclid距离"""
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return distance


def construct_distance_matrix(loc):
    """构造距离矩阵（默认为非对称图）"""
    distance_matrix = {}
    for node1 in loc.keys():
        for node2 in loc.keys():
            if node1 != node2:
                distance_matrix[node1, node2] = calculate_euclid_distance(loc[node1][0], loc[node1][1],
                                                                          loc[node2][0], loc[node2][1])
    # 获取字典DistanceMatrix中最大的值
    key = max(distance_matrix, key=distance_matrix.get)
    longest_distance = distance_matrix[key]
    return distance_matrix, longest_distance


def construct_time_matrix(veh, dist_mat):
    """  构造通行时间矩阵.
    具体描述：对于车辆k，若其速度为sk，点i到点j的距离为dij，那么其从点i行驶到点j所用的时间tijk=dij/sk
    """
    time_matrix = {}
    for k in veh.keys():
        for i, j in dist_mat.keys():
            if veh[k][1] == 0:
                time_matrix[i, j, k] = dist_mat[i, j] / 1
            else:
                time_matrix[i, j, k] = dist_mat[i, j] / veh[k][1]
    return time_matrix


def build_pdptw_model(veh, loc, dem, time_w, serv_time, req, task_no_list, e_time, l_time, dist_mat, lon_dist, time_mat):
    """使用Gurobi建立PDPTW问题的模型"""
    
    # 创建模型
    model = Model("PDPTW Model")

    # 创建变量
    x_index = {}  # 存储变量xijk的下标ijk，表示车辆k是否经过弧ij
    q_index = {}  # 存储变量qik的下标ik，表示车辆k即将离开i时的载货量
    b_index = {}  # 存储变量bik的下标ik，表示车辆k开始服务i的时间
    for k in veh.keys():
        for node1 in task_no_list:
            q_index[node1, k] = 0
            b_index[node1, k] = 0
            if node1 == task_no_list[0]:
                for node2 in task_no_list[1:]:
                    x_index[node1, node2, k] = 0
            elif node1 == task_no_list[-1]:
                continue
            else:
                for node2 in task_no_list[1:]:
                    if node1 != node2:
                        x_index[node1, node2, k] = 0
    x = model.addVars(x_index.keys(), vtype=GRB.BINARY, name='x')  # 变量x_{ijk}
    q = model.addVars(q_index.keys(), vtype=GRB.INTEGER, name='q')  # 变量q_{ik}
    b = model.addVars(b_index.keys(), vtype=GRB.CONTINUOUS, name='b')  # 变量b_{ik}

    # ==================VRPTW===================

    # 约束（1）every vertex has to be served exactly once，除了depot外，每个节点只被服务一次
    for cus in task_no_list[1:-1]:
        model.addConstr(x.sum(cus, '*', '*') == 1)

    # 约束(2-3) guarantee that every vehicle starts at the depot and returns to the depot
    # at the end of its route. 每辆车必须从depot出发，最后回到depot
    # 约束(4) Flow conservation 流平衡约束
    for k in veh.keys():
        model.addConstr(x.sum(task_no_list[0], '*', k) == 1)  # 车辆k从depot出发
        model.addConstr(x.sum('*', task_no_list[-1], k) == 1)  # 车辆k回到depot
        for cus in task_no_list[1:-1]:  # 车辆k在P和D点（客户点）的流平衡约束
            model.addConstr(x.sum(cus, '*', k) == x.sum('*', cus, k))

    # 约束 (5) Time variables are used to eliminate subtours,用时间变量来消除子回路约束
    # 需要用大M法来线性化该约束，M定义为 2*(LatestTime+LongestDistance)
    for i in x_index.keys():
        model.addConstr(b[i[1], i[2]] + 2 * (1 - x[i]) * (l_time + lon_dist) >= b[i[0], i[2]] + serv_time[i[0]] +
                        time_mat[i])

    # 约束(6-7) guarantee that a vehicle’s capacity is not exceeded throughout its tour，载货量平衡与车辆载量约束
    # 约束(6) 载货量平衡约束，需要用大M法来线性化该约束，M定义为 100*车辆最大载量
    for i in x_index.keys():
        model.addConstr(q[i[1], i[2]] + (1 - x[i]) * (100 * veh[i[2]][0]) >= q[i[0], i[2]] + dem[i[1]])

    # 约束（7）车辆载量约束
    for i in q_index.keys():
        model.addConstr(q[i] >= 0)
        model.addConstr(q[i] >= dem[i[0]])
        model.addConstr(q[i] <= veh[i[1]][0])
        model.addConstr(q[i] <= veh[i[1]][0] + dem[i[0]])

    # 约束（8）depot和customer的时间窗约束
    for k in veh.keys():
        # depot的时间窗约束
        model.addConstr(b[task_no_list[0], k] >= time_w[task_no_list[0]][0])
        model.addConstr(b[task_no_list[0], k] <= time_w[task_no_list[0]][1])
        model.addConstr(b[task_no_list[-1], k] >= time_w[task_no_list[-1]][0])
        model.addConstr(b[task_no_list[-1], k] <= time_w[task_no_list[-1]][1])
        for j in range(len(req)):
            # 运输请求i两个节点的左时间窗
            model.addConstr(b[req[j][0], k] >= time_w[req[j][0]][0])
            model.addConstr(b[req[j][1], k] >= time_w[req[j][1]][0])
            # 运输请求i两个节点的右时间窗
            model.addConstr(b[req[j][0], k] <= time_w[req[j][0]][1])
            model.addConstr(b[req[j][1], k] <= time_w[req[j][1]][1])

    # ==================PDPTW===================

    # 添加了以下两个约束后，使得VRPTW问题变成了PDPTW问题

    # 约束（9）both origin and destination of a request must be served by the same vehicle
    # 保证取货后要有对应的送货，取货和送货由同一辆车完成
    for i in range(len(req)):
        for k in veh.keys():
            model.addConstr(x.sum(req[i][0], '*', k) == x.sum('*', req[i][1], k))

    # 约束 (10) delivery can only occur after pickup,先取后送货约束
    for i in range(len(req)):
        for k in veh.keys():
            model.addConstr(b[req[i][0], k] <= b[req[i][1], k])

    # 设置目标函数:最小化车辆行驶距离
    c3_distance_cost = 0
    for k in veh.keys():
        for node1 in task_no_list:
            if node1 == task_no_list[0]:
                for node2 in task_no_list[1:]:
                    c3_distance_cost += (dist_mat[node1, node2] * x[node1, node2, k])
            elif node1 == task_no_list[-1]:
                continue
            else:
                for node2 in task_no_list[1:]:
                    if node1 != node2:
                        c3_distance_cost += (dist_mat[node1, node2] * x[node1, node2, k])
    total_cost = c3_distance_cost
    model.setObjective(total_cost, GRB.MINIMIZE)
    model.update()

    model.__data = x, b, q

    return model, x_index, total_cost


def out_put_solution(mod, sol_x, sol_b, sol_q, veh, task_no_list, file_name):
    print('==========================================================')
    # with open('%s.log' % file_name, 'w') as f:
    # mod.setParam(GRB.Param.LogFile, '%s.log' % file_name)
    print('总成本：', mod.ObjVal)
    veh_count = 0
    for k in veh.keys():
        if sol_x[task_no_list[0], task_no_list[-1], k].x > 0.5:
            continue
        veh_count += 1
        print('route for vehicle {}：'.format(k))
        for node1 in task_no_list:
            if node1 == task_no_list[0]:
                for node2 in task_no_list[1:]:
                    if sol_x[node1, node2, k].x > 0.5:
                        print('%s-->%s' % (node1, node2))
            elif node1 == task_no_list[-1]:
                continue
            else:
                for node2 in task_no_list[1:]:
                    if node1 != node2 and sol_x[node1, node2, k].x > 0.5:
                        print('%s-->%s' % (node1, node2))
    print('共使用{}辆车'.format(veh_count))


if __name__ == '__main__':
    start = time.time()
    # 数据文件路径
    data_path = './LiLimPDPTWbenchmark/pdptw100_revised/lr104.txt'
    log_file_name = data_path[-9:-4]
    # 读取数据
    vehicles, locations, demand, time_window, service_time, request, earliest_time, latest_time, task_no_list = \
        read_pdptw_benchmark_data(data_path)
    # 构建距离和时间矩阵
    distance_matrix, longest_distance = construct_distance_matrix(locations)
    time_matrix = construct_time_matrix(vehicles, distance_matrix)
    # 创建Gurobi模型并优化
    model, x_index, total_cost = build_pdptw_model(vehicles, locations, demand, time_window, service_time, request,
                                                   task_no_list, earliest_time, latest_time, distance_matrix,
                                                   longest_distance, time_matrix)
    model.setParam(GRB.Param.LogFile, './gurobi_log/pdptw100_%s.log' % log_file_name)
    model.optimize()
    # 输出结果
    x, b, q = model.__data
    out_put_solution(model, x, b, q, vehicles, task_no_list, log_file_name)
    end = time.time()
    print('程序总的运行时间：', end - start, '秒')

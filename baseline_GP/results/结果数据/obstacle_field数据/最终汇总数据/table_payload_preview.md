# Obstacle-field merged table payload

## single_static_metrics

| 地图 | T_first | T_all | success（%） | detection（%） | obs（%） | path |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | 47.0 | 153.7 | 50.0 | 83.3 | 62.6 | 196.8 |
| open_water | 48.7 | 166.4 | 50.0 | 83.3 | 60.9 | 203.2 |
| obstacle_field | 38.5 | 117.3 | 60.0 | 86.7 | 56.1 | 166.4 |
| peninsula_passage | 53.9 | 192.2 | 40.0 | 80.0 | 70.9 | 220.9 |

## single_static_counts

| 地图 | n | n_first | n_all |
| --- | --- | --- | --- |
| 总体 | 30 | 30 | 15 |
| open_water | 10 | 10 | 5 |
| obstacle_field | 10 | 10 | 6 |
| peninsula_passage | 10 | 10 | 4 |

## single_random_metrics

| 地图 | T_first | T_all | success（%） | detection（%） | obs（%） | path |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | 60.5 | 145.6 | 63.3 | 86.7 | 61.5 | 180.2 |
| open_water | 71.1 | 125.4 | 70.0 | 90.0 | 53.6 | 159.8 |
| obstacle_field | 54.7 | 138.0 | 60.0 | 83.3 | 62.6 | 178.8 |
| peninsula_passage | 55.8 | 176.7 | 60.0 | 86.7 | 68.4 | 202.0 |

## single_random_counts

| 地图 | n | n_first | n_all |
| --- | --- | --- | --- |
| 总体 | 30 | 30 | 19 |
| open_water | 10 | 10 | 7 |
| obstacle_field | 10 | 10 | 6 |
| peninsula_passage | 10 | 10 | 6 |

## two_static_assignment

| 地图 | 方法 | T_first | T_all | success（%） | detection（%） | obs（%） | duplicate（%） | cross（%） | wait |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 总体 | independent | 80.3 | 156.5 | 26.7 | 61.1 | 56.6 | 4.9 | 32.3 | 0.7 |
| open_water | independent | 76.9 | 141.8 | 40.0 | 60.0 | 49.6 | 0.9 | 28.1 | 0.6 |
| obstacle_field | independent | 51.5 | 157.7 | 30.0 | 70.0 | 59.5 | 7.8 | 26.7 | 1.2 |
| peninsula_passage | independent | 111.9 | 212.0 | 10.0 | 53.3 | 60.5 | 6.0 | 42.1 | 0.3 |
| 总体 | coordinated | 64.1 | 171.3 | 46.7 | 77.8 | 70.4 | 0.0 | 1.8 | 0.0 |
| open_water | coordinated | 73.7 | 128.8 | 40.0 | 70.0 | 65.9 | 0.0 | 3.0 | 0.0 |
| obstacle_field | coordinated | 46.9 | 168.4 | 50.0 | 80.0 | 72.0 | 0.0 | 0.9 | 0.0 |
| peninsula_passage | coordinated | 71.6 | 208.2 | 50.0 | 83.3 | 73.2 | 0.0 | 1.4 | 0.0 |

## two_static_counts

| 地图 | 方法 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | independent | 30 | 28 | 8 |
| open_water | independent | 10 | 8 | 4 |
| obstacle_field | independent | 10 | 10 | 3 |
| peninsula_passage | independent | 10 | 10 | 1 |
| 总体 | coordinated | 30 | 30 | 14 |
| open_water | coordinated | 10 | 10 | 4 |
| obstacle_field | coordinated | 10 | 10 | 5 |
| peninsula_passage | coordinated | 10 | 10 | 5 |

## two_static_delta

| 地图 | ΔT_first | ΔT_all | Δsuccess（百分点） | Δdetection（百分点） | Δduplicate（百分点） | Δcross（百分点） | Δwait |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 总体 | -22.6 | -4.8 | +20.0 | +16.7 | -4.9 | -30.5 | -0.7 |
| open_water | -23.0 | -3.0 | 0.0 | +10.0 | -0.9 | -25.1 | -0.6 |
| obstacle_field | -4.6 | -7.5 | +20.0 | +10.0 | -7.8 | -25.8 | -1.2 |
| peninsula_passage | -40.3 | N/A | +40.0 | +30.0 | -6.0 | -40.7 | -0.3 |

## two_random_assignment

| 地图 | 方法 | T_first | T_all | success（%） | detection（%） | obs（%） | duplicate（%） | cross（%） | wait |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 总体 | independent | 69.3 | 176.8 | 43.3 | 75.6 | 68.5 | 3.8 | 36.0 | 0.4 |
| open_water | independent | 90.1 | 179.4 | 50.0 | 76.7 | 65.5 | 4.4 | 27.4 | 0.3 |
| obstacle_field | independent | 45.3 | 147.0 | 30.0 | 73.3 | 71.7 | 3.7 | 41.5 | 0.9 |
| peninsula_passage | independent | 72.5 | 192.0 | 50.0 | 76.7 | 68.4 | 3.3 | 39.1 | 0.0 |
| 总体 | coordinated | 60.1 | 175.6 | 53.3 | 83.3 | 74.2 | 0.0 | 2.5 | 0.0 |
| open_water | coordinated | 64.7 | 180.8 | 60.0 | 83.3 | 73.4 | 0.0 | 0.3 | 0.0 |
| obstacle_field | coordinated | 49.9 | 181.0 | 50.0 | 83.3 | 77.5 | 0.0 | 0.5 | 0.0 |
| peninsula_passage | coordinated | 65.6 | 164.0 | 50.0 | 83.3 | 71.8 | 0.0 | 6.7 | 0.0 |

## two_random_counts

| 地图 | 方法 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | independent | 30 | 30 | 13 |
| open_water | independent | 10 | 10 | 5 |
| obstacle_field | independent | 10 | 10 | 3 |
| peninsula_passage | independent | 10 | 10 | 5 |
| 总体 | coordinated | 30 | 30 | 16 |
| open_water | coordinated | 10 | 10 | 6 |
| obstacle_field | coordinated | 10 | 10 | 5 |
| peninsula_passage | coordinated | 10 | 10 | 5 |

## two_random_delta

| 地图 | ΔT_first | ΔT_all | Δsuccess（百分点） | Δdetection（百分点） | Δduplicate（百分点） | Δcross（百分点） | Δwait |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 总体 | -9.2 | -5.4 | +10.0 | +7.8 | -3.8 | -33.5 | -0.4 |
| open_water | -25.4 | -24.3 | +10.0 | +6.7 | -4.4 | -27.1 | -0.3 |
| obstacle_field | +4.6 | +27.5 | +20.0 | +10.0 | -3.7 | -41.0 | -0.9 |
| peninsula_passage | -6.9 | -8.3 | 0.0 | +6.7 | -3.3 | -32.4 | 0.0 |

## single_static_anomaly

| 地图 | 采集方式 | T_first | T_all | success（%） | detection（%） | obs（%） |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | UCB | 47.0 | 153.7 | 50.0 | 83.3 | 62.6 |
| open_water | UCB | 48.7 | 166.4 | 50.0 | 83.3 | 60.9 |
| obstacle_field | UCB | 38.5 | 117.3 | 60.0 | 86.7 | 56.1 |
| peninsula_passage | UCB | 53.9 | 192.2 | 40.0 | 80.0 | 70.9 |
| 总体 | anomaly_upper_tail | 49.0 | 160.2 | 73.3 | 88.9 | 61.3 |
| open_water | anomaly_upper_tail | 47.4 | 149.8 | 80.0 | 90.0 | 56.0 |
| obstacle_field | anomaly_upper_tail | 41.9 | 139.1 | 70.0 | 86.7 | 57.9 |
| peninsula_passage | anomaly_upper_tail | 57.8 | 193.3 | 70.0 | 90.0 | 70.1 |

## single_static_anomaly_counts

| 地图 | 采集方式 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | UCB | 30 | 30 | 15 |
| open_water | UCB | 10 | 10 | 5 |
| obstacle_field | UCB | 10 | 10 | 6 |
| peninsula_passage | UCB | 10 | 10 | 4 |
| 总体 | anomaly_upper_tail | 30 | 30 | 22 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 |
| obstacle_field | anomaly_upper_tail | 10 | 10 | 7 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 7 |

## single_random_anomaly

| 地图 | 采集方式 | T_first | T_all | success（%） | detection（%） | obs（%） |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | UCB | 60.5 | 145.6 | 63.3 | 86.7 | 61.5 |
| open_water | UCB | 71.1 | 125.4 | 70.0 | 90.0 | 53.6 |
| obstacle_field | UCB | 54.7 | 138.0 | 60.0 | 83.3 | 62.6 |
| peninsula_passage | UCB | 55.8 | 176.7 | 60.0 | 86.7 | 68.4 |
| 总体 | anomaly_upper_tail | 46.9 | 162.9 | 70.0 | 87.8 | 65.2 |
| open_water | anomaly_upper_tail | 56.2 | 173.2 | 80.0 | 86.7 | 66.5 |
| obstacle_field | anomaly_upper_tail | 35.2 | 139.4 | 80.0 | 93.3 | 56.7 |
| peninsula_passage | anomaly_upper_tail | 49.4 | 183.8 | 50.0 | 83.3 | 72.2 |

## single_random_anomaly_counts

| 地图 | 采集方式 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | UCB | 30 | 30 | 19 |
| open_water | UCB | 10 | 10 | 7 |
| obstacle_field | UCB | 10 | 10 | 6 |
| peninsula_passage | UCB | 10 | 10 | 6 |
| 总体 | anomaly_upper_tail | 30 | 30 | 21 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 |
| obstacle_field | anomaly_upper_tail | 10 | 10 | 8 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 5 |

## single_anomaly_delta

| 目标模式 | 地图 | ΔT_first | ΔT_all | Δsuccess（百分点） | Δdetection（百分点） | Δobs（百分点） |
| --- | --- | --- | --- | --- | --- | --- |
| static | 总体 | +2.0 | -4.7 | +23.3 | +5.6 | -1.3 |
| static | open_water | -1.3 | -14.4 | +30.0 | +6.7 | -4.9 |
| static | obstacle_field | +3.4 | +9.8 | +10.0 | 0.0 | +1.9 |
| static | peninsula_passage | +3.9 | -7.0 | +30.0 | +10.0 | -0.8 |
| random_walk | 总体 | -13.6 | +20.5 | +6.7 | +1.1 | +3.6 |
| random_walk | open_water | -14.9 | +44.6 | +10.0 | -3.3 | +13.0 |
| random_walk | obstacle_field | -19.5 | -17.2 | +20.0 | +10.0 | -5.9 |
| random_walk | peninsula_passage | -6.4 | +14.7 | -10.0 | -3.3 | +3.9 |

## two_static_anomaly

| 地图 | 采集方式 | T_first | T_all | success（%） | detection（%） | obs（%） |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | UCB | 64.1 | 171.3 | 46.7 | 77.8 | 70.4 |
| open_water | UCB | 73.7 | 128.8 | 40.0 | 70.0 | 65.9 |
| obstacle_field | UCB | 46.9 | 168.4 | 50.0 | 80.0 | 72.0 |
| peninsula_passage | UCB | 71.6 | 208.2 | 50.0 | 83.3 | 73.2 |
| 总体 | anomaly_upper_tail | 58.9 | 149.1 | 43.3 | 77.8 | 64.5 |
| open_water | anomaly_upper_tail | 63.0 | 110.5 | 40.0 | 73.3 | 64.0 |
| obstacle_field | anomaly_upper_tail | 48.5 | 142.0 | 40.0 | 80.0 | 65.2 |
| peninsula_passage | anomaly_upper_tail | 65.2 | 185.6 | 50.0 | 80.0 | 64.3 |

## two_static_anomaly_counts

| 地图 | 采集方式 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | UCB | 30 | 30 | 14 |
| open_water | UCB | 10 | 10 | 4 |
| obstacle_field | UCB | 10 | 10 | 5 |
| peninsula_passage | UCB | 10 | 10 | 5 |
| 总体 | anomaly_upper_tail | 30 | 30 | 13 |
| open_water | anomaly_upper_tail | 10 | 10 | 4 |
| obstacle_field | anomaly_upper_tail | 10 | 10 | 4 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 5 |

## two_random_anomaly

| 地图 | 采集方式 | T_first | T_all | success（%） | detection（%） | obs（%） |
| --- | --- | --- | --- | --- | --- | --- |
| 总体 | UCB | 60.1 | 175.6 | 53.3 | 83.3 | 74.2 |
| open_water | UCB | 64.7 | 180.8 | 60.0 | 83.3 | 73.4 |
| obstacle_field | UCB | 49.9 | 181.0 | 50.0 | 83.3 | 77.5 |
| peninsula_passage | UCB | 65.6 | 164.0 | 50.0 | 83.3 | 71.8 |
| 总体 | anomaly_upper_tail | 65.0 | 145.3 | 66.7 | 85.6 | 65.4 |
| open_water | anomaly_upper_tail | 63.7 | 141.1 | 80.0 | 93.3 | 61.6 |
| obstacle_field | anomaly_upper_tail | 50.5 | 139.2 | 60.0 | 86.7 | 66.3 |
| peninsula_passage | anomaly_upper_tail | 80.8 | 157.2 | 60.0 | 76.7 | 68.2 |

## two_random_anomaly_counts

| 地图 | 采集方式 | n | n_first | n_all |
| --- | --- | --- | --- | --- |
| 总体 | UCB | 30 | 30 | 16 |
| open_water | UCB | 10 | 10 | 6 |
| obstacle_field | UCB | 10 | 10 | 5 |
| peninsula_passage | UCB | 10 | 10 | 5 |
| 总体 | anomaly_upper_tail | 30 | 30 | 20 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 |
| obstacle_field | anomaly_upper_tail | 10 | 10 | 6 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 6 |

## two_anomaly_delta

| 目标模式 | 地图 | ΔT_first | ΔT_all | Δsuccess（百分点） | Δdetection（百分点） | Δobs（百分点） |
| --- | --- | --- | --- | --- | --- | --- |
| static | 总体 | -5.2 | +1.8 | -3.3 | -0.0 | -5.9 |
| static | open_water | -10.7 | -9.5 | 0.0 | +3.3 | -2.0 |
| static | obstacle_field | +1.6 | +54.0 | -10.0 | -0.0 | -6.8 |
| static | peninsula_passage | -6.4 | -18.8 | 0.0 | -3.3 | -8.9 |
| random_walk | 总体 | +4.9 | -29.4 | +13.3 | +2.2 | -8.9 |
| random_walk | open_water | -1.0 | -30.0 | +20.0 | +10.0 | -11.8 |
| random_walk | obstacle_field | +0.6 | -49.5 | +10.0 | +3.3 | -11.2 |
| random_walk | peninsula_passage | +15.2 | -8.5 | +10.0 | -6.7 | -3.6 |


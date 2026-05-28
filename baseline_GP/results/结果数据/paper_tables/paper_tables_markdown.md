# Paper Tables — simple_ring_v1 Mainline

## 6.2 单 USV 已知地图搜索基线及目标运动鲁棒性实验

### 表 6-1 单艇 static UCB 结果

| map_kind | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_first_detection_std | time_to_all_found_mean | time_to_all_found_std | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean | path_length_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 30 | 30 | 14 | 45.300 | 21.197 | 158.286 | 47.041 | 0.467 | 0.811 | 2.433 | 0.652 | 201.867 |
| open_water | 10 | 10 | 5 | 48.700 | 19.805 | 166.400 | 55.491 | 0.500 | 0.833 | 2.500 | 0.609 | 203.200 |
| harbor_cove | 10 | 10 | 5 | 33.300 | 13.191 | 123.000 | 25.534 | 0.500 | 0.800 | 2.400 | 0.637 | 181.500 |
| peninsula_passage | 10 | 10 | 4 | 53.900 | 25.031 | 192.250 | 29.848 | 0.400 | 0.800 | 2.400 | 0.709 | 220.900 |


### 表 6-2 单艇 random_walk UCB 结果

| map_kind | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_first_detection_std | time_to_all_found_mean | time_to_all_found_std | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean | path_length_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 30 | 30 | 17 | 53.167 | 35.817 | 153.059 | 55.433 | 0.567 | 0.856 | 2.567 | 0.648 | 190.733 |
| open_water | 10 | 10 | 7 | 71.100 | 50.065 | 125.429 | 58.460 | 0.700 | 0.900 | 2.700 | 0.536 | 159.800 |
| harbor_cove | 10 | 10 | 4 | 32.600 | 14.645 | 166.000 | 61.725 | 0.400 | 0.800 | 2.400 | 0.725 | 210.400 |
| peninsula_passage | 10 | 10 | 6 | 55.800 | 24.031 | 176.667 | 39.677 | 0.600 | 0.867 | 2.600 | 0.684 | 202.000 |


## 6.3 双 USV 协同搜索实验

### 表 6-3 static coordinated vs independent

| target_motion_mode | map_kind | assignment_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean | duplicate_viewpoint_ratio_mean | cross_region_assignment_ratio_mean | wait_count_total_mean | reservation_wait_fallback_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| static | ALL | independent | 30 | 28 | 9 | 83.036 | 142.778 | 0.300 | 0.611 | 1.833 | 0.595 | 0.032 | 0.304 | 0.300 | 0.000 |
| static | open_water | independent | 10 | 8 | 4 | 76.875 | 141.750 | 0.400 | 0.600 | 1.800 | 0.496 | 0.009 | 0.281 | 0.600 | 0.000 |
| static | harbor_cove | independent | 10 | 10 | 4 | 59.100 | 126.500 | 0.400 | 0.700 | 2.100 | 0.685 | 0.028 | 0.211 | 0.000 | 0.000 |
| static | peninsula_passage | independent | 10 | 10 | 1 | 111.900 | 212.000 | 0.100 | 0.533 | 1.600 | 0.605 | 0.060 | 0.421 | 0.300 | 0.000 |
| static | ALL | coordinated | 30 | 30 | 13 | 64.533 | 159.231 | 0.433 | 0.744 | 2.233 | 0.699 | 0.000 | 0.019 | 0.000 | 0.000 |
| static | open_water | coordinated | 10 | 10 | 4 | 73.700 | 128.750 | 0.400 | 0.700 | 2.100 | 0.659 | 0.000 | 0.030 | 0.000 | 0.000 |
| static | harbor_cove | coordinated | 10 | 10 | 4 | 48.300 | 128.500 | 0.400 | 0.700 | 2.100 | 0.706 | 0.000 | 0.014 | 0.000 | 0.000 |
| static | peninsula_passage | coordinated | 10 | 10 | 5 | 71.600 | 208.200 | 0.500 | 0.833 | 2.500 | 0.732 | 0.000 | 0.014 | 0.000 | 0.000 |


### 表 6-4 random_walk coordinated vs independent

| target_motion_mode | map_kind | assignment_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean | duplicate_viewpoint_ratio_mean | cross_region_assignment_ratio_mean | wait_count_total_mean | reservation_wait_fallback_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_walk | ALL | independent | 30 | 30 | 16 | 75.800 | 172.688 | 0.533 | 0.800 | 2.400 | 0.691 | 0.029 | 0.265 | 0.100 | 0.000 |
| random_walk | open_water | independent | 10 | 10 | 5 | 90.100 | 179.400 | 0.500 | 0.767 | 2.300 | 0.655 | 0.044 | 0.274 | 0.300 | 0.000 |
| random_walk | harbor_cove | independent | 10 | 10 | 6 | 64.800 | 151.000 | 0.600 | 0.867 | 2.600 | 0.735 | 0.012 | 0.132 | 0.000 | 0.000 |
| random_walk | peninsula_passage | independent | 10 | 10 | 5 | 72.500 | 192.000 | 0.500 | 0.767 | 2.300 | 0.684 | 0.033 | 0.391 | 0.000 | 0.000 |
| random_walk | ALL | coordinated | 30 | 30 | 14 | 60.500 | 171.071 | 0.467 | 0.811 | 2.433 | 0.756 | 0.000 | 0.025 | 0.000 | 0.000 |
| random_walk | open_water | coordinated | 10 | 10 | 6 | 64.700 | 180.833 | 0.600 | 0.833 | 2.500 | 0.734 | 0.000 | 0.003 | 0.000 | 0.000 |
| random_walk | harbor_cove | coordinated | 10 | 10 | 3 | 51.200 | 163.333 | 0.300 | 0.767 | 2.300 | 0.815 | 0.000 | 0.007 | 0.000 | 0.000 |
| random_walk | peninsula_passage | coordinated | 10 | 10 | 5 | 65.600 | 164.000 | 0.500 | 0.833 | 2.500 | 0.718 | 0.000 | 0.067 | 0.000 | 0.000 |


### 表 6-5 static coordinated − independent 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_duplicate_viewpoint_ratio_mean | delta_cross_region_assignment_ratio_mean | delta_wait_count_total_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | -24.821 | 12.600 | 0.133 | 0.133 | 0.400 | -0.032 | -0.285 | -0.300 |
| open_water | -23.000 | -3.000 | 0.000 | 0.100 | 0.300 | -0.009 | -0.251 | -0.600 |
| harbor_cove | -10.800 | 36.000 | 0.000 | 0.000 | 0.000 | -0.028 | -0.197 | 0.000 |
| peninsula_passage | -40.300 | N/A | 0.400 | 0.300 | 0.900 | -0.060 | -0.407 | -0.300 |


### 表 6-6 random_walk coordinated − independent 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_duplicate_viewpoint_ratio_mean | delta_cross_region_assignment_ratio_mean | delta_wait_count_total_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | -15.300 | -8.125 | -0.067 | 0.011 | 0.033 | -0.029 | -0.240 | -0.100 |
| open_water | -25.400 | -24.333 | 0.100 | 0.067 | 0.200 | -0.044 | -0.271 | -0.300 |
| harbor_cove | -13.600 | 16.500 | -0.300 | -0.100 | -0.300 | -0.012 | -0.125 | 0.000 |
| peninsula_passage | -6.900 | -8.333 | 0.000 | 0.067 | 0.200 | -0.033 | -0.324 | 0.000 |


## 6.4 anomaly-aware acquisition 消融实验

### 表 6-7 单艇 static UCB vs anomaly

| map_kind | clue_acquisition_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | ucb | 30 | 30 | 14 | 45.300 | 158.286 | 0.467 | 0.811 | 2.433 | 0.652 |
| open_water | ucb | 10 | 10 | 5 | 48.700 | 166.400 | 0.500 | 0.833 | 2.500 | 0.609 |
| harbor_cove | ucb | 10 | 10 | 5 | 33.300 | 123.000 | 0.500 | 0.800 | 2.400 | 0.637 |
| peninsula_passage | ucb | 10 | 10 | 4 | 53.900 | 192.250 | 0.400 | 0.800 | 2.400 | 0.709 |
| ALL | anomaly_upper_tail | 30 | 30 | 22 | 45.800 | 163.091 | 0.733 | 0.900 | 2.700 | 0.633 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 | 47.400 | 149.750 | 0.800 | 0.900 | 2.700 | 0.560 |
| harbor_cove | anomaly_upper_tail | 10 | 10 | 7 | 32.200 | 148.143 | 0.700 | 0.900 | 2.700 | 0.639 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 7 | 57.800 | 193.286 | 0.700 | 0.900 | 2.700 | 0.701 |


### 表 6-8 单艇 random_walk UCB vs anomaly

| map_kind | clue_acquisition_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | ucb | 30 | 30 | 17 | 53.167 | 153.059 | 0.567 | 0.856 | 2.567 | 0.648 |
| open_water | ucb | 10 | 10 | 7 | 71.100 | 125.429 | 0.700 | 0.900 | 2.700 | 0.536 |
| harbor_cove | ucb | 10 | 10 | 4 | 32.600 | 166.000 | 0.400 | 0.800 | 2.400 | 0.725 |
| peninsula_passage | ucb | 10 | 10 | 6 | 55.800 | 176.667 | 0.600 | 0.867 | 2.600 | 0.684 |
| ALL | anomaly_upper_tail | 30 | 30 | 20 | 46.000 | 166.400 | 0.667 | 0.867 | 2.600 | 0.677 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 | 56.200 | 173.250 | 0.800 | 0.867 | 2.600 | 0.665 |
| harbor_cove | anomaly_upper_tail | 10 | 10 | 7 | 32.400 | 146.143 | 0.700 | 0.900 | 2.700 | 0.644 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 5 | 49.400 | 183.800 | 0.500 | 0.833 | 2.500 | 0.722 |


### 表 6-9 双艇 coordinated static UCB vs anomaly

| map_kind | clue_acquisition_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | ucb | 30 | 30 | 13 | 64.533 | 159.231 | 0.433 | 0.744 | 2.233 | 0.699 |
| open_water | ucb | 10 | 10 | 4 | 73.700 | 128.750 | 0.400 | 0.700 | 2.100 | 0.659 |
| harbor_cove | ucb | 10 | 10 | 4 | 48.300 | 128.500 | 0.400 | 0.700 | 2.100 | 0.706 |
| peninsula_passage | ucb | 10 | 10 | 5 | 71.600 | 208.200 | 0.500 | 0.833 | 2.500 | 0.732 |
| ALL | anomaly_upper_tail | 30 | 30 | 12 | 56.733 | 135.333 | 0.400 | 0.744 | 2.233 | 0.669 |
| open_water | anomaly_upper_tail | 10 | 10 | 4 | 63.000 | 110.500 | 0.400 | 0.733 | 2.200 | 0.640 |
| harbor_cove | anomaly_upper_tail | 10 | 10 | 3 | 42.000 | 84.667 | 0.300 | 0.700 | 2.100 | 0.724 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 5 | 65.200 | 185.600 | 0.500 | 0.800 | 2.400 | 0.643 |


### 表 6-10 双艇 coordinated random_walk UCB vs anomaly

| map_kind | clue_acquisition_mode | n | n_first_detected | n_all_found | time_to_first_detection_mean | time_to_all_found_mean | success_all_found_mean | detection_rate_mean | found_count_mean | known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | ucb | 30 | 30 | 14 | 60.500 | 171.071 | 0.467 | 0.811 | 2.433 | 0.756 |
| open_water | ucb | 10 | 10 | 6 | 64.700 | 180.833 | 0.600 | 0.833 | 2.500 | 0.734 |
| harbor_cove | ucb | 10 | 10 | 3 | 51.200 | 163.333 | 0.300 | 0.767 | 2.300 | 0.815 |
| peninsula_passage | ucb | 10 | 10 | 5 | 65.600 | 164.000 | 0.500 | 0.833 | 2.500 | 0.718 |
| ALL | anomaly_upper_tail | 30 | 30 | 20 | 62.967 | 157.100 | 0.667 | 0.856 | 2.567 | 0.697 |
| open_water | anomaly_upper_tail | 10 | 10 | 8 | 63.700 | 141.125 | 0.800 | 0.933 | 2.800 | 0.616 |
| harbor_cove | anomaly_upper_tail | 10 | 10 | 6 | 44.400 | 178.333 | 0.600 | 0.867 | 2.600 | 0.794 |
| peninsula_passage | anomaly_upper_tail | 10 | 10 | 6 | 80.800 | 157.167 | 0.600 | 0.767 | 2.300 | 0.682 |


### 表 6-11 单艇 static UCB vs anomaly — anomaly − UCB 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | 0.500 | -0.786 | 0.267 | 0.089 | 0.267 | -0.019 |
| open_water | -1.300 | -14.400 | 0.300 | 0.067 | 0.200 | -0.049 |
| harbor_cove | -1.100 | 17.800 | 0.200 | 0.100 | 0.300 | 0.002 |
| peninsula_passage | 3.900 | -7.000 | 0.300 | 0.100 | 0.300 | -0.008 |


### 表 6-12 单艇 random_walk UCB vs anomaly — anomaly − UCB 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | -7.167 | 14.214 | 0.100 | 0.011 | 0.033 | 0.029 |
| open_water | -14.900 | 44.571 | 0.100 | -0.033 | -0.100 | 0.130 |
| harbor_cove | -0.200 | -39.250 | 0.300 | 0.100 | 0.300 | -0.081 |
| peninsula_passage | -6.400 | 14.667 | -0.100 | -0.033 | -0.100 | 0.039 |


### 表 6-13 双艇 coordinated static UCB vs anomaly — anomaly − UCB 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | -7.800 | -25.375 | -0.033 | 0.000 | 0.000 | -0.030 |
| open_water | -10.700 | -9.500 | 0.000 | 0.033 | 0.100 | -0.020 |
| harbor_cove | -6.300 | -54.500 | -0.100 | 0.000 | 0.000 | 0.018 |
| peninsula_passage | -6.400 | -18.750 | 0.000 | -0.033 | -0.100 | -0.089 |


### 表 6-14 双艇 coordinated random_walk UCB vs anomaly — anomaly − UCB 差值

| map_kind | delta_time_to_first_detection_mean | delta_time_to_all_found_mean | delta_success_all_found_mean | delta_detection_rate_mean | delta_found_count_mean | delta_known_free_observation_ratio_final_mean |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | 2.467 | -9.417 | 0.200 | 0.044 | 0.133 | -0.059 |
| open_water | -1.000 | -30.000 | 0.200 | 0.100 | 0.300 | -0.118 |
| harbor_cove | -6.800 | 23.667 | 0.300 | 0.100 | 0.300 | -0.021 |
| peninsula_passage | 15.200 | -8.500 | 0.100 | -0.067 | -0.200 | -0.036 |



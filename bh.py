# -*- coding:utf-8 -*-
import os
import json
import time
import pandas
import logging
import datetime
import requests
import traceback
import SendMail as sm
class FooError(ValueError):
    pass
class Log:
    def __init__(self):
        path = './dealfile/'
        if not os.path.exists(path):
            os.mkdir(path)
        self.file_path = os.path.join(path, '{0}.log'.format(datetime.datetime.now().strftime('%Y-%m-%d')))

    def write(self, msg):
        with open(self.file_path, 'a') as f:
            f.write('{0}: {1}\n'.format(datetime.datetime.now(), msg))
class ReportDataCheck(object):
    def __init__(self, report_json):
        self.report_json = report_json
        self.ErrorInfo = []
    def spread_overview_check(self):
        spread_overview = self.report_json['spread_overview']
        trend_post, platform_post, accoun_web_user, accoun_web_post, kol_user_post = 0, 0, 0, 0, 0
        # 传播实况
        trend_post = sum([tren['post_count'] for tren in spread_overview['trend']])
        platform_post = sum(platform['value'] for platform in spread_overview['platform_web'])
        for accoun_web in spread_overview['account_web']:
            accoun_web_user += accoun_web['account']
            accoun_web_post += accoun_web['post_count']
            if accoun_web['user_type'].upper() == 'KOL':
                kol_user_post = accoun_web['account']
        try:
            assert trend_post == spread_overview['post_count'] == len(spread_overview['post_detail']) == platform_post == accoun_web_post
            assert accoun_web_user == spread_overview['account_count']
        except Exception as e:
            self.ErrorInfo.append(traceback.format_exc())
            # raise FooError('传播实况 >> 报告活动贴数&&发帖人数 AssertError Failed')
        try:
            assert len(self.report_json['spread_efficiency_rank']['article']) == (10 if trend_post > 10 else trend_post)
            assert len(self.report_json['spread_efficiency_rank']['kol']) == (10 if kol_user_post > 10 else kol_user_post)
        except Exception as e:
            self.ErrorInfo.append(traceback.format_exc())
            # raise FooError('传播实况 >> 传播效率排行top10 AssertError Failed')
        try:
            start_date = self.report_json['report_config']['start_date']
            end_date = self.report_json['report_config']['end_date']
            if date_diff(start_date, end_date) > 30:
                # 监控天数 > 30, 按周返回数据
                assert week_diff(start_date, end_date) == len(spread_overview['trend'])
        except Exception as e:
            self.ErrorInfo.append(traceback.format_exc())
            # raise FooError('传播实况 >> 活动贴投放趋势周级返回 AssertError Failed')
    def spread_efficiency_check(self):
        spread_efficiency = self.report_json['spread_efficiency']
        accoun_fans_effiency, accoun_interaction_effiency, accoun_breadth_effiency = 0, 0, 0
        activi_fans_effiency, activi_interaction_effiency, activi_breadth_effiency = 0, 0, 0
        platfo_fans_effiency, platfo_interaction_effiency, platfo_breadth_effiency = 0, 0, 0
        # 传播效率
        for platform in spread_efficiency['platform_web']:
            platfo_breadth_effiency += platform['breadth']
            platfo_interaction_effiency += platform['interaction']
            platfo_fans_effiency += platform['fans_count']
        for activi in spread_efficiency['activity_web']:
            activi_breadth_effiency += activi['breadth']
            activi_interaction_effiency += activi['interaction']
            activi_fans_effiency += activi['fans_count']
        for accoun_web in spread_efficiency['account_web']:
            accoun_breadth_effiency += accoun_web['breadth']
            accoun_interaction_effiency += accoun_web['interaction']
            accoun_fans_effiency += accoun_web['fans_count']
        try:
            assert accoun_interaction_effiency == platfo_interaction_effiency
            assert accoun_breadth_effiency == platfo_breadth_effiency
            # 加入只有一个子活动标签与 各子活动粉丝数和相等
            if len(self.report_json['spread_overview']['activity']) == 1:
                assert platfo_fans_effiency == accoun_fans_effiency
        except AssertionError as e:
            self.ErrorInfo.append(traceback.format_exc())
            print('传播效率',self.ErrorInfo)
            # raise FooError('传播效率 >> 传播效率传播广度计算 AssertError Failed')
    def spread_effectiveness_check(self):
        spread_effectiveness = self.report_json['spread_effectiveness']
        # ugc
        son_activi_brand, son_activi_no_brand, br_brand, br_no_brand = 0, 0, 0, 0
        for activi in spread_effectiveness['activity_ugc_in']:
            son_activi_brand = activi['value'] + son_activi_brand
            son_activi_no_brand = activi['unvalue'] + son_activi_no_brand
        for br in spread_effectiveness['ugc_in_activity_composition']:
            if br['name'] == '提及品牌':
                br_brand = br['value']
            else:
                br_no_brand = br['value']
        try:
            # print(spread_effectiveness['ugc_in_activity_count'], son_activi_brand + son_activi_no_brand)
            if len(self.report_json['spread_overview']['activity']) == 1:
                # 加入判断只有一个子活动时，有此判断
                assert (br_brand == son_activi_brand) and (son_activi_no_brand == br_no_brand)
                assert spread_effectiveness['ugc_in_activity_count'] == son_activi_brand + son_activi_no_brand
        except Exception as e:
            print('ugc', e)
            self.ErrorInfo.append(traceback.format_exc())
            # raise FooError('UGC >> 只有一个子活动数据 AssertError Failed')
        try:
            # 品牌关注度/认知度
            assert (len(self.report_json['brand_concern']['trend']) == 13) and (len(self.report_json['tags_concern']['trend']) == 13)
        except:
            self.ErrorInfo.append(traceback.format_exc())
            #raise FooError('品牌关注度/认知度 >> 品牌关注度/认知度 AssertError Failed')

class HttpSearchReport(object):
    def __init__(self):
        self.errors = {}
        self.header = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
            'Connection': 'close'
        }
    def login(self, username, password):
        url = 'http://tracking.marcpoint.com/api/user/login/'
        name_pwd = {
            'username': username,
            'password': password
        }
        cookie_repon = requests.post(url=url, headers=self.header, data=name_pwd)
        self.header['Cookie'] = 'sessionid={0}'.format(cookie_repon.json()['sessionid'])
        return cookie_repon.json()['sessionid']
    def searchReportId(self):
        url = 'http://tracking.marcpoint.com/api/apps/report/report-config-list/'
        data_send = {
            'report_status': 100,
            'monitor_end_time': 36500,
            'monitor_cycle': 36500,
            'key_word': ''
        }
        try:
            time.sleep(3)
            report_info = {}
            respon_list = requests.post(url=url, headers=self.header, data=data_send)
            for repo in respon_list.json():
                report_info[str(repo['id'])] = {}
                report_info[str(repo['id'])]['id'] = repo['id']
                report_info[str(repo['id'])]['name'] = repo['name']
                report_info[str(repo['id'])]['status'] = repo['status']
                report_info[str(repo['id'])]['status_values'] = repo['status_values']
                report_info[str(repo['id'])]['username'] = repo['username']
            print('正在查询报告列表')
            return report_info
        except Exception as e:
            cont = 'http://tracking.marcpoint.com/marketingAnalysis/evaluation'
            self.errors['0'] = '报告列表查询:\n url:{0}\n'.format(cont) + traceback.format_exc()
            # raise FooError('查询报告列表api返回错误')
    def searchReport(self, report_id, report_name):
        url = 'http://tracking.marcpoint.com/api/apps/report/report-details/'
        data_send = {
            'report_id': report_id
        }
        time.sleep(3)
        try:
            respon = requests.post(url=url, headers=self.header, data=data_send)
            assert respon.status_code == 200
            # None 代表未找到新的生成完成的报告
            assert respon.json()['report_config']['status'] == 0
            return respon.json()
        except Exception as e:
            cont = 'http://tracking.marcpoint.com/reportContent?report_id={0}'.format(report_id)
            self.errors[report_id] = '报告:{0}\n url:{1}\n'.format(report_name, cont) + traceback.format_exc()
            # raise FooError('当前报告详情页接口报错，没有数据')

    def __del__(self):
        url = 'http://tracking.marcpoint.com/api/user/logout/'
        cookie_repon = requests.get(url=url, headers=self.header)
        assert cookie_repon.json()['item'] == 'success'
def date_diff(start_date, end_date):
    d1 = time.strptime(start_date, '%Y-%m-%d')
    d2 = time.strptime(end_date, '%Y-%m-%d')
    das = (datetime.datetime(d1.tm_year, d1.tm_mon, d1.tm_mday) - datetime.datetime(d2.tm_year, d2.tm_mon, d2.tm_mday)).days
    return abs(das)
def week_diff(start_date, end_date):
    d1 = time.strptime(start_date, '%Y-%m-%d')
    d2 = time.strptime(end_date, '%Y-%m-%d')
    w1 = datetime.date(d1.tm_year, d1.tm_mon, d1.tm_mday).isocalendar()[1]
    w2 = datetime.date(d2.tm_year, d2.tm_mon, d2.tm_mday).isocalendar()[1]
    return abs(w1 - w2) + 1

def main(username, password, mail_title, receiver):
    n, m = 0, 0
    error = ['searchReportId', 'spread_overview', 'spread_efficiency', 'spread_effectiveness']
    raw_status = {}

    while True:
        # 轮询报告,出现新报告,检查详情
        n += 1
        print('{0}次轮询'.format(n), '>>>>>')
        hsr = HttpSearchReport()
        hsr.login(username, password)
        # 获取报告列表信息结果
        report_list = hsr.searchReportId()
        if report_list:
            for k, v in report_list.items():
                # 更新被忽略报告id 列表
                if k in raw_status.keys():
                    if raw_status[k] != v['status_values']:
                        temp_id.remove(v['id'])
                        raw_status[k] = v['status_values']
                else:
                    raw_status[k] = v['status_values']
                if v['id'] in temp_id:
                    continue
                print('校验的报告：{0}'.format(k))
                print(temp_id, raw_status)
                try:
                    if v['status'] == -1:
                        temp_id.append(v['id'])
                        # print('发送成功')
                        sender.sendMail(subject='tracking线上监控', content='报告：{0}：{1}'.format(v['name'], '生成失败，请查看原因'), receive_mail=receiver)
                    elif v['status'] == 0:
                        # json_ = open(r'F:\宏原测试\测试项目\mock\tracking\report-details', 'r', encoding='utf-8')
                        report_info = hsr.searchReport(k, v['name'])
                        # report_info = json.loads(json_.read())
                        rdc = ReportDataCheck(report_info)
                        rdc.spread_overview_check()
                        rdc.spread_effectiveness_check()
                        rdc.spread_efficiency_check()
                        if rdc.ErrorInfo:
                            temp_id.append(v['id'])
                            # print('发送成功')
                            sender.sendMail(subject=mail_title, content='报告{0}：{1}'.format(v['name'], '\n'.join(rdc.ErrorInfo)), receive_mail=receiver)
                    temp_id.append(v['id'])
                except Exception as e:
                    print(e, 'sadaks')
            if hsr.errors:
                # print('发送成功', hsr.errors)
                temp_id.extend([int(_) for _ in hsr.errors.keys()])
                sender.sendMail(subject=mail_title, content='tracking{0}'.format('\n'.join([_ for _ in hsr.errors.values()])), receive_mail=receiver)
            time.sleep(5 * 60)

if __name__ == '__main__':
    # 临时忽略报告
    temp_id = [232, 233, 241, 39, 234, 242]
    temp_id = list(set(temp_id))
    log = Log()
    sender = sm.SendMailProject()
    
    sender.sendMail(subject='hello', content='测试使用', receive_mail=['operation@marcpoint.com'])


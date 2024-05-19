# AWSのcloud shellで下記コードを実行

import requests
import json
import ipaddress
import boto3

# 1つのSGには60ルールまで登録可能。
# また1つのEC2インスタンスのinterfaceにはSGを5個適用できる。
# 300以下に抑えるためには/15にする必要があった。
def aggre_prefix(ip_nw):
    src_nw = ipaddress.ip_network(ip_nw, strict=False)
    aggre_nw = str(src_nw.supernet(src_nw.prefixlen - 15)) if src_nw.prefixlen > 15 else ip_nw
    return aggre_nw

# listを均等に分割する関数 by Chatgpt
def split_list(lst, num_splits):
    avg = len(lst) // num_splits
    rem = len(lst) % num_splits
    result = [lst[i * avg + min(i, rem):(i + 1) * avg + min(i + 1, rem)] for i in range(num_splits)]
    return result

# IP-Permissionsを作成する関数
def make_ip_permissions(ip_nws):
    ip_permissions = [
        {
            "IpProtocol": "tcp",
            "FromPort": 2222,
            "ToPort": 2225,
            "IpRanges": [{"CidrIp": ip_nw} for ip_nw in ip_nws]
        }
    ]
    return ip_permissions

# Githubから使用するアドレスを取得し、ipv4だけをlistにする。
url = "https://api.github.com/meta"
github_ip_nw = requests.get(url)
json_github_ip_nw = github_ip_nw.json()
ip4_nws = [ip_nw for ip_nw in json_github_ip_nw['actions'] if ":" not in ip_nw]

# NWをaggregateする。
aggre_ip4_nws = list(set(aggre_prefix(ip4_nw) for ip4_nw in ip4_nws))

# NWのlistを5分割する。
split_aggre_ip4_nws = split_list(aggre_ip4_nws, 5)

# SGに設定するパラメータを作成
ip_permissions_list = [make_ip_permissions(aggre_ip4_nws) for aggre_ip4_nws in split_aggre_ip4_nws]

ec2_resource = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

# SGを5個作ってそれぞれにパラメータを当ててく
for i in range(5):
    res = ec2_client.create_security_group(Description="SG for GHA", GroupName=f"SG_for_GHA_{i}")
    security_group = ec2_resource.SecurityGroup(res["GroupId"])
    security_group.authorize_ingress(IpPermissions=ip_permissions_list[i])

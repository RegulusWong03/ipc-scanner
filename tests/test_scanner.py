"""核心扫描模块单元测试"""

import sys
import os
import ipaddress

# 将项目根目录加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanner.network import (
    get_network_interfaces,
    get_scan_range,
    parse_ip_range,
    mac_to_bytes,
    bytes_to_mac,
)
from scanner.port_scan import (
    scan_port,
    scan_ports,
    guess_brand,
    is_ipc_or_nvr,
    scan_host,
    COMMON_PORTS,
    BRAND_SIGNATURES,
)


class TestNetwork:
    """网络工具模块测试"""

    def test_get_network_interfaces(self):
        """测试网卡枚举"""
        ifaces = get_network_interfaces()
        assert isinstance(ifaces, list)
        # 至少有 lo 或其他网卡
        for iface in ifaces:
            assert "name" in iface
            assert "ip" in iface
            assert "netmask" in iface
            assert "broadcast" in iface
            # IP 不应是 127.x
            assert not iface["ip"].startswith("127.")

    def test_get_scan_range_24(self):
        """测试 /24 网段扫描范围"""
        hosts = get_scan_range("192.168.1.1", "255.255.255.0")
        assert len(hosts) == 254
        assert "192.168.1.1" in hosts
        assert "192.168.1.254" in hosts
        # 不应包含网络地址和广播地址
        assert "192.168.1.0" not in hosts
        assert "192.168.1.255" not in hosts

    def test_get_scan_range_max_hosts(self):
        """测试大网段截断"""
        hosts = get_scan_range("10.0.0.1", "255.255.0.0", max_hosts=50)
        assert len(hosts) == 50

    def test_parse_ip_range(self):
        """测试 CIDR 解析"""
        hosts = parse_ip_range("192.168.0.0/30")
        assert len(hosts) == 2
        assert "192.168.0.1" in hosts
        assert "192.168.0.2" in hosts

    def test_mac_to_bytes(self):
        """测试 MAC 转字节"""
        assert mac_to_bytes("aa:bb:cc:dd:ee:ff") == b"\xaa\xbb\xcc\xdd\xee\xff"
        assert mac_to_bytes("AA-BB-CC-DD-EE-FF") == b"\xaa\xbb\xcc\xdd\xee\xff"
        assert mac_to_bytes("aabbccddeeff") == b"\xaa\xbb\xcc\xdd\xee\xff"

    def test_bytes_to_mac(self):
        """测试字节转 MAC"""
        assert bytes_to_mac(b"\xaa\xbb\xcc\xdd\xee\xff") == "aa:bb:cc:dd:ee:ff"
        assert bytes_to_mac(b"\x00\x11\x22\x33\x44\x55") == "00:11:22:33:44:55"

    def test_mac_roundtrip(self):
        """测试 MAC 转换的往返一致性"""
        original = "ab:cd:ef:01:23:45"
        assert bytes_to_mac(mac_to_bytes(original)) == original


class TestPortScan:
    """端口扫描模块测试"""

    def test_scan_port_closed(self):
        """测试扫描关闭的端口"""
        # 假设本地 59999 端口未开放
        assert scan_port("127.0.0.1", 59999, timeout=0.1) is False

    def test_scan_ports_returns_list(self):
        """测试批量扫描返回正确格式"""
        results = scan_ports("127.0.0.1", [59998, 59999], timeout=0.1)
        assert isinstance(results, list)
        for item in results:
            assert "port" in item
            assert "service" in item

    def test_guess_brand_hikvision(self):
        """测试海康品牌识别"""
        ports = [
            {"port": 80, "service": "HTTP"},
            {"port": 8000, "service": "Hikvision"},
            {"port": 554, "service": "RTSP"},
        ]
        assert guess_brand(ports) == "hikvision"

    def test_guess_brand_dahua(self):
        """测试大华品牌识别"""
        ports = [
            {"port": 80, "service": "HTTP"},
            {"port": 37777, "service": "Dahua"},
            {"port": 554, "service": "RTSP"},
        ]
        assert guess_brand(ports) == "dahua"

    def test_guess_brand_unknown(self):
        """测试无法识别的品牌"""
        ports = [{"port": 80, "service": "HTTP"}]
        assert guess_brand(ports) == ""

    def test_is_ipc_or_nvr_with_rtsp(self):
        """测试有 RTSP 端口时识别为视频设备"""
        ports = [{"port": 554, "service": "RTSP"}]
        assert is_ipc_or_nvr(ports) == "IPC"

    def test_is_ipc_or_nvr_no_ports(self):
        """测试无开放端口"""
        assert is_ipc_or_nvr([]) == ""

    def test_scan_host_local(self):
        """测试扫描本地主机"""
        result = scan_host("127.0.0.1", timeout=0.1)
        assert "ip" in result
        assert "alive" in result
        assert "open_ports" in result
        assert "brand" in result
        assert "device_type" in result


class TestHikvisionSADP:
    """海康 SADP 协议测试（报文构造和解析）"""

    def test_parse_probe_match(self):
        """测试解析 ProbeMatch 响应 XML"""
        from protocols.hikvision import HikvisionSADP

        sadp = HikvisionSADP()

        # 模拟 ProbeMatch 响应
        xml = (
            b'<?xml version="1.0" encoding="utf-8"?>'
            b"<ProbeMatch>"
            b"<Uuid>test-uuid</Uuid>"
            b"<Types>inquiry</Types>"
            b"<DeviceDescription>DS-2CD2142FWD-I</DeviceDescription>"
            b"<DeviceSN>DS-2CD2142FWD-I20160920AAWR123456789</DeviceSN>"
            b"<DeviceType>1</DeviceType>"
            b"<MACAddress>aa:bb:cc:dd:ee:ff</MACAddress>"
            b"<IPAddress>192.168.1.64</IPAddress>"
            b"<IPv4SubnetMask>255.255.255.0</IPv4SubnetMask>"
            b"<IPv4Gateway>192.168.1.1</IPv4Gateway>"
            b"<DHCP>true</DHCP>"
            b"<DeviceVersion>V5.4.3 build 161018</DeviceVersion>"
            b"<DeviceFactoryDefault>true</DeviceFactoryDefault>"
            b"<Activate>false</Activate>"
            b"<DigitalChannels>1</DigitalChannels>"
            b"<AnalogChannels>0</AnalogChannels>"
            b"<HttpPort>80</HttpPort>"
            b"<RtspPort>554</RtspPort>"
            b"<DevicePort>8000</DevicePort>"
            b"</ProbeMatch>"
        )

        result = sadp._parse_probe_match(xml)
        assert result is not None
        assert result["brand"] == "hikvision"
        assert result["ip"] == "192.168.1.64"
        assert result["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result["model"] == "DS-2CD2142FWD-I"
        assert result["serial"] == "DS-2CD2142FWD-I20160920AAWR123456789"
        assert result["firmware"] == "V5.4.3 build 161018"
        assert result["device_type"] == "IPC"
        assert result["subnet"] == "255.255.255.0"
        assert result["gateway"] == "192.168.1.1"
        assert result["dhcp"] is True
        assert result["activated"] is False
        assert result["factory_default"] is True
        assert result["digital_channels"] == 1
        assert result["http_port"] == 80
        assert result["rtsp_port"] == 554
        assert result["device_port"] == 8000

    def test_parse_probe_match_invalid_xml(self):
        """测试解析无效 XML"""
        from protocols.hikvision import HikvisionSADP

        sadp = HikvisionSADP()
        assert sadp._parse_probe_match(b"not xml") is None
        assert sadp._parse_probe_match(b"<Other></Other>") is None

    def test_parse_modify_response_success(self):
        """测试解析成功修改响应"""
        from protocols.hikvision import HikvisionSADP

        sadp = HikvisionSADP()
        xml = (
            b'<?xml version="1.0" encoding="utf-8"?>'
            b"<ModifyDeviceResult>"
            b"<ResultCode>1</ResultCode>"
            b"<ResultMsg>Success</ResultMsg>"
            b"</ModifyDeviceResult>"
        )
        result = sadp._parse_modify_response(xml)
        assert result["success"] is True

    def test_parse_modify_response_failure(self):
        """测试解析失败修改响应"""
        from protocols.hikvision import HikvisionSADP

        sadp = HikvisionSADP()
        xml = (
            b'<?xml version="1.0" encoding="utf-8"?>'
            b"<ModifyDeviceResult>"
            b"<ResultCode>0</ResultCode>"
            b"<ResultMsg>Wrong password</ResultMsg>"
            b"</ModifyDeviceResult>"
        )
        result = sadp._parse_modify_response(xml)
        assert result["success"] is False
        assert "Wrong password" in result["message"]


class TestDahuaConfigTool:
    """大华 ConfigTool 协议测试（报文构造和解析）"""

    def test_parse_search_response(self):
        """测试解析搜索响应包"""
        from protocols.dahua import DahuaConfigTool

        dahua = DahuaConfigTool()

        # 构造模拟响应包
        packet = bytearray(200)
        # 头部
        packet[0:2] = b"\xf3\x00"
        import struct
        struct.pack_into("<H", packet, 2, 200)
        struct.pack_into("<H", packet, 4, 0x0006)

        # 设备型号 (offset 16, 16 bytes)
        model = b"IPC-HDW4431C-A\x00\x00"
        packet[16:32] = model

        # MAC 地址 (offset 32, 6 bytes)
        packet[32:38] = bytes.fromhex("3c15c2aabb11")

        # IP 地址 (offset 38, 16 bytes)
        ip = b"192.168.1.108\x00\x00\x00"
        packet[38:54] = ip

        # 子网掩码 (offset 54, 16 bytes)
        mask = b"255.255.255.0\x00\x00\x00"
        packet[54:70] = mask

        # 网关 (offset 70, 16 bytes)
        gw = b"192.168.1.1\x00\x00\x00\x00\x00"
        packet[70:86] = gw

        # TCP 端口 (offset 86, 2 bytes)
        struct.pack_into("<H", packet, 86, 37777)
        # HTTP 端口 (offset 88, 2 bytes)
        struct.pack_into("<H", packet, 88, 80)

        # 固件版本 (offset 90, 32 bytes)
        fw = b"2.800.0000000.0.R\x00" + b"\x00" * 14
        packet[90:122] = fw

        # 序列号 (offset 122, 32 bytes)
        sn = b"ABC12345678\x00" + b"\x00" * 20
        packet[122:154] = sn

        # 通道数 (offset 154)
        struct.pack_into("<H", packet, 154, 1)
        # 设备类型 (offset 156)
        struct.pack_into("<H", packet, 156, 0x01)  # IPC

        # DHCP (offset 174)
        packet[174] = 0x00  # 静态

        result = dahua._parse_search_response(bytes(packet), ("192.168.1.108", 5050))

        assert result is not None
        assert result["brand"] == "dahua"
        assert result["model"] == "IPC-HDW4431C-A"
        assert result["mac"] == "3c:15:c2:aa:bb:11"
        assert result["ip"] == "192.168.1.108"
        assert result["subnet"] == "255.255.255.0"
        assert result["gateway"] == "192.168.1.1"
        assert result["tcp_port"] == 37777
        assert result["http_port"] == 80
        assert result["firmware"] == "2.800.0000000.0.R"
        assert result["serial"] == "ABC12345678"
        assert result["channels"] == 1
        assert result["device_type"] == "IPC"
        assert result["dhcp"] is False

    def test_parse_search_response_too_short(self):
        """测试过短的包被拒绝"""
        from protocols.dahua import DahuaConfigTool

        dahua = DahuaConfigTool()
        assert dahua._parse_search_response(b"\xf3\x00" + b"\x00" * 50, ("", 0)) is None

    def test_parse_search_response_bad_magic(self):
        """测试无效头部被拒绝"""
        from protocols.dahua import DahuaConfigTool

        dahua = DahuaConfigTool()
        assert dahua._parse_search_response(b"\x00\x00" + b"\x00" * 200, ("", 0)) is None


class TestOnvifClient:
    """ONVIF 协议测试（报文解析）"""

    def test_parse_probe_match(self):
        """测试 WS-Discovery ProbeMatch 解析"""
        from protocols.onvif_client import _parse_probe_match

        xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"'
            b' xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
            b' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
            b'<SOAP-ENV:Header>'
            b'<wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</wsa:Action>'
            b'<wsa:MessageID>uuid:resp-uuid</wsa:MessageID>'
            b'<wsa:RelatesTo>uuid:my-uuid</wsa:RelatesTo>'
            b'</SOAP-ENV:Header>'
            b'<SOAP-ENV:Body>'
            b'<d:ProbeMatches><d:ProbeMatch>'
            b'<wsa:EndpointReference>'
            b'<wsa:Address>urn:uuid:device-123</wsa:Address>'
            b'</wsa:EndpointReference>'
            b'<d:Types>dn:NetworkVideoTransmitter</d:Types>'
            b'<d:Scopes>onvif://www.onvif.org/Profile/Streaming</d:Scopes>'
            b'<d:XAddrs>http://192.168.1.100:80/onvif/device_service</d:XAddrs>'
            b'<d:MetadataVersion>1</d:MetadataVersion>'
            b'</d:ProbeMatch></d:ProbeMatches>'
            b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
        )

        result = _parse_probe_match(xml)
        assert result is not None
        assert "http://192.168.1.100:80/onvif/device_service" in result["xaddrs"]
        assert "urn:uuid:device-123" in result["endpoint"]

    def test_parse_probe_match_invalid(self):
        """测试无效 ProbeMatch"""
        from protocols.onvif_client import _parse_probe_match

        assert _parse_probe_match(b"not xml") is None
        assert _parse_probe_match(b"<root></root>") is None

    def test_extract_ip_port(self):
        """测试从 URL 提取 IP 和端口"""
        from protocols.onvif_client import _extract_ip_port

        ip, port = _extract_ip_port("http://192.168.1.100:8080/onvif/device_service")
        assert ip == "192.168.1.100"
        assert port == 8080

        ip, port = _extract_ip_port("http://10.0.0.1/onvif/device_service")
        assert ip == "10.0.0.1"
        assert port == 80

    def test_parse_system_date_time(self):
        """测试解析 GetSystemDateAndTime 响应"""
        from protocols.onvif_client import _parse_system_date_time

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
            ' xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
            '<s:Body><tds:GetSystemDateAndTimeResponse>'
            '<tds:SystemDateAndTime>'
            '<tds:DateTimeType>NTP</tds:DateTimeType>'
            '<tds:DaylightSavings>false</tds:DaylightSavings>'
            '<tds:UTCDateTime>'
            '<tds:Time><tds:Hour>14</tds:Hour><tds:Minute>30</tds:Minute>'
            '<tds:Second>45</tds:Second></tds:Time>'
            '<tds:Date><tds:Year>2026</tds:Year><tds:Month>9</tds:Month>'
            '<tds:Day>29</tds:Day></tds:Date>'
            '</tds:UTCDateTime>'
            '</tds:SystemDateAndTime>'
            '</tds:GetSystemDateAndTimeResponse></s:Body></s:Envelope>'
        )

        result = _parse_system_date_time(xml)
        assert result is not None
        assert result["year"] == 2026
        assert result["month"] == 9
        assert result["day"] == 29
        assert result["hour"] == 14
        assert result["minute"] == 30
        assert result["second"] == 45


class TestDeviceModel:
    """设备数据模型测试"""

    def test_device_creation(self):
        """测试 Device 对象创建"""
        from device.models import Device, DeviceStatus, DeviceType

        device = Device(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.100")
        assert device.mac == "aa:bb:cc:dd:ee:ff"
        assert device.ip == "192.168.1.100"
        assert device.status == DeviceStatus.OFFLINE
        assert device.device_type == DeviceType.UNKNOWN

    def test_device_status_enum(self):
        """测试状态枚举"""
        from device.models import DeviceStatus

        assert DeviceStatus.ONLINE.value == "在线"
        assert DeviceStatus.OFFLINE.value == "离线"
        assert DeviceStatus.NEW.value == "新上线"


class TestStorage:
    """SQLite 存储测试"""

    def test_save_and_load(self, tmp_path):
        """测试设备保存和加载"""
        from device import storage
        from device.models import Device, DeviceType, DeviceStatus

        # 使用临时数据库
        storage.DB_PATH = tmp_path / "test_devices.db"
        storage.init_db()

        device = Device(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.100",
            brand="hikvision",
            model="DS-2CD2142FWD-I",
            device_type=DeviceType.IPC,
            status=DeviceStatus.ONLINE,
            channels=1,
        )
        storage.save_device(device)

        loaded = storage.load_devices()
        assert len(loaded) == 1
        assert loaded[0].mac == "aa:bb:cc:dd:ee:ff"
        assert loaded[0].ip == "192.168.1.100"
        assert loaded[0].brand == "hikvision"
        assert loaded[0].model == "DS-2CD2142FWD-I"

    def test_upsert_by_mac(self, tmp_path):
        """测试 MAC 唯一键的更新行为"""
        from device import storage
        from device.models import Device, DeviceType, DeviceStatus

        storage.DB_PATH = tmp_path / "test_devices.db"
        storage.init_db()

        # 保存初始记录
        d1 = Device(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.100", brand="hikvision")
        storage.save_device(d1)

        # IP 变更后再次保存（同 MAC）
        d2 = Device(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.200", brand="hikvision")
        storage.save_device(d2)

        loaded = storage.load_devices()
        assert len(loaded) == 1  # 应该只有一条记录
        assert loaded[0].ip == "192.168.1.200"  # IP 已更新


if __name__ == "__main__":
    # 运行所有测试
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

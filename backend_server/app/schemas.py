from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PolicyBase(BaseModel):
    name: str
    mode: str
    target_app_package: Optional[str] = None
    target_hdmi_port: Optional[int] = None
    fallback_mode: Optional[str] = "app"
    fallback_value: Optional[str] = None
    is_active: bool = True

class PolicyCreate(PolicyBase):
    pass

class PolicyOut(PolicyBase):
    id: int
    class Config:
        from_attributes = True

class DeviceRegister(BaseModel):
    device_sn: str
    device_name: str
    room_name: Optional[str] = None # New field
    model_name: Optional[str] = None
    wifi_mac: Optional[str] = None
    eth_mac: Optional[str] = None

class DeviceHeartbeatIn(BaseModel):
    wifi_ip: Optional[str] = None
    eth_ip: Optional[str] = None
    wifi_mac: Optional[str] = None
    eth_mac: Optional[str] = None
    network_ssid: Optional[str] = None
    installed_apps: Optional[str] = None
    ram_usage: Optional[str] = None # New field
    storage_usage: Optional[str] = None # New field
    status: str = "ok"
    message: Optional[str] = None

class DeviceOut(BaseModel):
    id: int
    device_sn: str
    device_name: str
    room_name: Optional[str] # New field
    model_name: Optional[str]
    wifi_ip: Optional[str]
    eth_ip: Optional[str]
    wifi_mac: Optional[str]
    eth_mac: Optional[str]
    network_ssid: Optional[str]
    installed_apps: Optional[str]
    ram_usage: Optional[str] # New field
    storage_usage: Optional[str] # New field
    online: bool
    policy_id: Optional[int]
    class Config:
        from_attributes = True

class OperationLogOut(BaseModel):
    id: int
    device_id: Optional[int]
    device_name: Optional[str]
    action: str
    detail: Optional[str]
    operator: str
    created_at: datetime
    class Config:
        from_attributes = True

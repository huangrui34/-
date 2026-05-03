from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    target_app_package: Mapped[str | None] = mapped_column(String(256), nullable=True)
    target_hdmi_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fallback_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_sn: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    room_name: Mapped[str | None] = mapped_column(String(128), nullable=True) # New field
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    android_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True) # Legacy field
    wifi_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eth_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wifi_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    eth_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network_ssid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "wifi" | "ethernet" | "none"
    wifi_rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wifi_frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wifi_link_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ping_latency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ping_packet_loss: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installed_apps: Mapped[str | None] = mapped_column(Text, nullable=True)
    ram_usage: Mapped[str | None] = mapped_column(String(64), nullable=True) # New field
    storage_usage: Mapped[str | None] = mapped_column(String(64), nullable=True) # New field
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"), nullable=True)
    policy_paused: Mapped[bool] = mapped_column(Boolean, default=False)  # 策略暂停状态
    wifi_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {ssid, security, password, identity, hidden}
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    policy = relationship("Policy")

class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class OperationLog(Base):
    __tablename__ = "operation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(128), default="admin")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

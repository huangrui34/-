#!/usr/bin/env python3
"""
测试运行脚本
支持多种测试模式和报告生成
"""
import os
import sys
import argparse
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

def setup_test_environment():
    """设置测试环境"""
    print("设置测试环境...")
    
    # 检查Python依赖
    try:
        import pytest
        import requests
        import sqlalchemy
        print("✓ 测试依赖已安装")
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        print("正在安装测试依赖...")
        
        requirements_file = PROJECT_ROOT / "backend_server" / "requirements.txt"
        if requirements_file.exists():
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], check=True)
        
        # 安装测试额外依赖
        test_requirements = ["pytest", "pytest-cov", "pytest-html", "pytest-xdist", "requests"]
        subprocess.run([sys.executable, "-m", "pip", "install"] + test_requirements, check=True)
        
        print("✓ 测试依赖安装完成")
    
    # 创建测试结果目录
    results_dir = PROJECT_ROOT / "tests" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试数据目录
    test_data_dir = PROJECT_ROOT / "tests" / "test_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    print("✓ 测试环境设置完成")

def run_unit_tests(output_dir, parallel=False):
    """运行单元测试"""
    print("\n" + "="*60)
    print("运行单元测试")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(PROJECT_ROOT / "tests" / "unit"),
        "-v",
        "--tb=short",
        f"--html={output_dir / 'unit_test_report.html'}",
        f"--junitxml={output_dir / 'unit_test_results.xml'}",
        "--cov=backend_server.app",
        "--cov-report=html",
        f"--cov-report=html:{output_dir / 'unit_coverage'}",
        "--markers=unit"
    ]
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    print(f"执行命令: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # 保存输出
    with open(output_dir / "unit_test_output.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
    
    print(f"单元测试完成，耗时: {duration:.2f}秒")
    print(f"退出码: {result.returncode}")
    
    return {
        "type": "unit",
        "duration": duration,
        "exit_code": result.returncode,
        "output_file": str(output_dir / "unit_test_output.log"),
        "report_file": str(output_dir / "unit_test_report.html"),
        "coverage_dir": str(output_dir / "unit_coverage")
    }

def run_integration_tests(output_dir):
    """运行集成测试"""
    print("\n" + "="*60)
    print("运行集成测试")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(PROJECT_ROOT / "tests" / "integration"),
        "-v",
        "--tb=short",
        f"--html={output_dir / 'integration_test_report.html'}",
        f"--junitxml={output_dir / 'integration_test_results.xml'}",
        "--markers=integration"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # 保存输出
    with open(output_dir / "integration_test_output.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
    
    print(f"集成测试完成，耗时: {duration:.2f}秒")
    print(f"退出码: {result.returncode}")
    
    return {
        "type": "integration",
        "duration": duration,
        "exit_code": result.returncode,
        "output_file": str(output_dir / "integration_test_output.log"),
        "report_file": str(output_dir / "integration_test_report.html")
    }

def run_e2e_tests(output_dir, tv_ip=None):
    """运行端到端测试"""
    print("\n" + "="*60)
    print("运行端到端测试")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(PROJECT_ROOT / "tests" / "e2e"),
        "-v",
        "--tb=short",
        f"--html={output_dir / 'e2e_test_report.html'}",
        f"--junitxml={output_dir / 'e2e_test_results.xml'}",
        "--markers=e2e"
    ]
    
    if tv_ip:
        cmd.extend(["--tv-ip", tv_ip])
    
    print(f"执行命令: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # 保存输出
    with open(output_dir / "e2e_test_output.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
    
    print(f"端到端测试完成，耗时: {duration:.2f}秒")
    print(f"退出码: {result.returncode}")
    
    return {
        "type": "e2e",
        "duration": duration,
        "exit_code": result.returncode,
        "output_file": str(output_dir / "e2e_test_output.log"),
        "report_file": str(output_dir / "e2e_test_report.html")
    }

def run_performance_tests(output_dir):
    """运行性能测试"""
    print("\n" + "="*60)
    print("运行性能测试")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(PROJECT_ROOT / "tests" / "performance"),
        "-v",
        "--tb=short",
        f"--html={output_dir / 'performance_test_report.html'}",
        f"--junitxml={output_dir / 'performance_test_results.xml'}",
        "--markers=performance"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # 保存输出
    with open(output_dir / "performance_test_output.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
    
    print(f"性能测试完成，耗时: {duration:.2f}秒")
    print(f"退出码: {result.returncode}")
    
    return {
        "type": "performance",
        "duration": duration,
        "exit_code": result.returncode,
        "output_file": str(output_dir / "performance_test_output.log"),
        "report_file": str(output_dir / "performance_test_report.html")
    }

def parse_junit_xml(xml_file):
    """解析JUnit XML测试结果"""
    if not xml_file.exists():
        return None
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        testsuites = root.findall("testsuite")
        if not testsuites:
            testsuites = [root]
        
        results = []
        for testsuite in testsuites:
            suite_result = {
                "name": testsuite.get("name", "unknown"),
                "tests": int(testsuite.get("tests", 0)),
                "failures": int(testsuite.get("failures", 0)),
                "errors": int(testsuite.get("errors", 0)),
                "skipped": int(testsuite.get("skipped", 0)),
                "time": float(testsuite.get("time", 0)),
                "testcases": []
            }
            
            for testcase in testsuite.findall("testcase"):
                case_result = {
                    "name": testcase.get("name", ""),
                    "classname": testcase.get("classname", ""),
                    "time": float(testcase.get("time", 0)),
                    "status": "passed"
                }
                
                # 检查是否有失败或错误
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")
                
                if failure is not None:
                    case_result["status"] = "failed"
                    case_result["failure"] = {
                        "message": failure.get("message", ""),
                        "type": failure.get("type", "")
                    }
                elif error is not None:
                    case_result["status"] = "error"
                    case_result["error"] = {
                        "message": error.get("message", ""),
                        "type": error.get("type", "")
                    }
                elif skipped is not None:
                    case_result["status"] = "skipped"
                    case_result["skipped"] = {
                        "message": skipped.get("message", "")
                    }
                
                suite_result["testcases"].append(case_result)
            
            results.append(suite_result)
        
        return results
    except Exception as e:
        print(f"解析JUnit XML失败: {e}")
        return None

def generate_summary_report(test_results, output_dir):
    """生成测试总结报告"""
    print("\n" + "="*60)
    print("生成测试总结报告")
    print("="*60)
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_duration": 0,
        "total_tests": 0,
        "total_passed": 0,
        "total_failed": 0,
        "total_errors": 0,
        "total_skipped": 0,
        "test_suites": [],
        "overall_status": "PASSED"
    }
    
    # 收集各测试套件结果
    for result in test_results:
        if "type" not in result:
            continue
        
        # 解析JUnit XML结果
        xml_file = output_dir / f"{result['type']}_test_results.xml"
        junit_results = parse_junit_xml(xml_file)
        
        if junit_results:
            for suite in junit_results:
                suite_summary = {
                    "type": result["type"],
                    "name": suite["name"],
                    "tests": suite["tests"],
                    "passed": suite["tests"] - suite["failures"] - suite["errors"] - suite["skipped"],
                    "failures": suite["failures"],
                    "errors": suite["errors"],
                    "skipped": suite["skipped"],
                    "duration": suite["time"],
                    "exit_code": result.get("exit_code", 0)
                }
                
                summary["test_suites"].append(suite_summary)
                
                # 更新总计
                summary["total_tests"] += suite["tests"]
                summary["total_passed"] += suite_summary["passed"]
                summary["total_failed"] += suite["failures"]
                summary["total_errors"] += suite["errors"]
                summary["total_skipped"] += suite["skipped"]
                summary["total_duration"] += result.get("duration", 0)
        
        else:
            # 如果没有XML结果，使用基本数据
            suite_summary = {
                "type": result["type"],
                "name": f"{result['type']}_tests",
                "tests": 0,
                "passed": 0,
                "failures": 0,
                "errors": 0 if result.get("exit_code") == 0 else 1,
                "skipped": 0,
                "duration": result.get("duration", 0),
                "exit_code": result.get("exit_code", 0)
            }
            
            summary["test_suites"].append(suite_summary)
    
    # 计算总体状态
    if summary["total_failed"] > 0 or summary["total_errors"] > 0:
        summary["overall_status"] = "FAILED"
    elif summary["total_tests"] == 0:
        summary["overall_status"] = "NO_TESTS"
    
    # 计算通过率
    if summary["total_tests"] > 0:
        summary["pass_rate"] = (summary["total_passed"] / summary["total_tests"]) * 100
    else:
        summary["pass_rate"] = 0
    
    # 保存JSON报告
    json_file = output_dir / "test_summary.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 生成文本报告
    txt_file = output_dir / "test_summary.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("="*60 + "\n")
        f.write("测试总结报告\n")
        f.write("="*60 + "\n\n")
        
        f.write(f"测试时间: {summary['timestamp']}\n")
        f.write(f"总体状态: {summary['overall_status']}\n")
        f.write(f"总耗时: {summary['total_duration']:.2f}秒\n")
        f.write(f"总测试数: {summary['total_tests']}\n")
        f.write(f"通过数: {summary['total_passed']}\n")
        f.write(f"失败数: {summary['total_failed']}\n")
        f.write(f"错误数: {summary['total_errors']}\n")
        f.write(f"跳过数: {summary['total_skipped']}\n")
        f.write(f"通过率: {summary['pass_rate']:.2f}%\n\n")
        
        f.write("测试套件详情:\n")
        f.write("-"*60 + "\n")
        
        for suite in summary["test_suites"]:
            f.write(f"\n{suite['type'].upper()}测试 - {suite['name']}:\n")
            f.write(f"  测试数: {suite['tests']}\n")
            f.write(f"  通过数: {suite['passed']}\n")
            f.write(f"  失败数: {suite['failures']}\n")
            f.write(f"  错误数: {suite['errors']}\n")
            f.write(f"  跳过数: {suite['skipped']}\n")
            f.write(f"  耗时: {suite['duration']:.2f}秒\n")
            f.write(f"  退出码: {suite['exit_code']}\n")
    
    print(f"总结报告已生成:")
    print(f"  JSON报告: {json_file}")
    print(f"  文本报告: {txt_file}")
    
    # 打印总结
    print("\n" + "="*60)
    print("测试执行总结")
    print("="*60)
    print(f"总体状态: {summary['overall_status']}")
    print(f"总测试数: {summary['total_tests']}")
    print(f"通过数: {summary['total_passed']} ({summary['pass_rate']:.2f}%)")
    print(f"失败数: {summary['total_failed']}")
    print(f"错误数: {summary['total_errors']}")
    print(f"跳过数: {summary['total_skipped']}")
    print(f"总耗时: {summary['total_duration']:.2f}秒")
    
    return summary

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行自动化测试套件")
    parser.add_argument("--mode", choices=["all", "unit", "integration", "e2e", "performance"], 
                       default="all", help="测试模式")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    parser.add_argument("--tv-ip", default=None, help="测试电视机IP地址")
    parser.add_argument("--parallel", action="store_true", help="并行运行单元测试")
    parser.add_argument("--setup-only", action="store_true", help="仅设置环境，不运行测试")
    parser.add_argument("--report-only", action="store_true", help="仅生成报告，不运行测试")
    
    args = parser.parse_args()
    
    # 设置输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "tests" / "results" / f"test_run_{timestamp}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"测试输出目录: {output_dir}")
    
    # 设置测试环境
    setup_test_environment()
    
    if args.setup_only:
        print("环境设置完成，退出")
        return 0
    
    # 运行测试
    test_results = []
    
    if args.mode in ["all", "unit"]:
        unit_result = run_unit_tests(output_dir, args.parallel)
        test_results.append(unit_result)
    
    if args.mode in ["all", "integration"]:
        integration_result = run_integration_tests(output_dir)
        test_results.append(integration_result)
    
    if args.mode in ["all", "e2e"]:
        e2e_result = run_e2e_tests(output_dir, args.tv_ip)
        test_results.append(e2e_result)
    
    if args.mode in ["all", "performance"]:
        performance_result = run_performance_tests(output_dir)
        test_results.append(performance_result)
    
    # 生成总结报告
    summary = generate_summary_report(test_results, output_dir)
    
    # 返回退出码
    if summary["overall_status"] == "FAILED":
        print("\n测试失败！")
        return 1
    elif summary["overall_status"] == "NO_TESTS":
        print("\n没有找到测试！")
        return 2
    else:
        print("\n测试通过！")
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
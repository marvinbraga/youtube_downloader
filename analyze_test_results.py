#!/usr/bin/env python3
"""
Analyze YT-DLP Test Results

This script parses the log file from the configuration tests and generates
a comprehensive report on which configurations work best.
"""

import re
from collections import defaultdict
from datetime import datetime

def parse_log_file(log_file_path):
    """Parse the test log file and extract test results."""
    results = []
    current_test = {}
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Match test configuration start
            if "Testing configuration:" in line:
                if current_test:
                    results.append(current_test)
                
                # Extract test name
                match = re.search(r'Testing configuration: (.+)', line)
                if match:
                    current_test = {
                        'test_name': match.group(1),
                        'success': False,
                        'error': None,
                        'download_time': None,
                        'file_size': None,
                        'video_title': None
                    }
            
            # Extract URL
            elif "URL:" in line and current_test:
                match = re.search(r'URL: (.+)', line)
                if match:
                    current_test['url'] = match.group(1)
            
            # Extract player clients
            elif "Player clients:" in line and current_test:
                match = re.search(r'Player clients: (.+)', line)
                if match:
                    current_test['player_clients'] = match.group(1)
            
            # Extract user agent info
            elif "User agent:" in line and current_test:
                match = re.search(r'User agent: (.+)', line)
                if match:
                    current_test['user_agent'] = match.group(1)
            
            # Extract success info
            elif "SUCCESS - Downloaded:" in line and current_test:
                current_test['success'] = True
                # Extract file size
                size_match = re.search(r'\((\d+) bytes\)', line)
                if size_match:
                    current_test['file_size'] = int(size_match.group(1))
                # Extract video title
                title_match = re.search(r'SUCCESS - Downloaded: (.+?)\.mp4', line)
                if title_match:
                    current_test['video_title'] = title_match.group(1)
            
            # Extract test completion time
            elif "Test completed in" in line and current_test:
                match = re.search(r'Test completed in ([\d.]+) seconds', line)
                if match:
                    current_test['download_time'] = float(match.group(1))
            
            # Extract error messages
            elif ("Download failed:" in line or "Info extraction failed:" in line or 
                  "Configuration error:" in line) and current_test:
                match = re.search(r'(Download failed|Info extraction failed|Configuration error): (.+)', line)
                if match:
                    current_test['error'] = match.group(2)
    
    # Add the last test if exists
    if current_test:
        results.append(current_test)
    
    return results

def analyze_results(results):
    """Analyze test results and generate comprehensive report."""
    
    if not results:
        return "No test results found to analyze."
    
    total_tests = len(results)
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    success_count = len(successful_tests)
    success_rate = (success_count / total_tests) * 100 if total_tests > 0 else 0
    
    # Analyze by configuration type
    client_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'avg_time': 0, 'times': []})
    user_agent_stats = defaultdict(lambda: {'total': 0, 'success': 0})
    url_stats = defaultdict(lambda: {'total': 0, 'success': 0})
    
    for result in results:
        # Client analysis
        clients = result.get('player_clients', 'Unknown')
        client_stats[clients]['total'] += 1
        if result['success']:
            client_stats[clients]['success'] += 1
            if result.get('download_time'):
                client_stats[clients]['times'].append(result['download_time'])
        
        # User agent analysis
        ua = result.get('user_agent', 'Unknown')
        if ua.startswith('Mozilla') and 'Chrome' in ua:
            ua_key = 'Chrome Windows'
        elif ua == 'Default':
            ua_key = 'Default'
        else:
            ua_key = ua[:30] + '...' if len(ua) > 30 else ua
        
        user_agent_stats[ua_key]['total'] += 1
        if result['success']:
            user_agent_stats[ua_key]['success'] += 1
        
        # URL analysis
        url = result.get('url', 'Unknown')
        if 'dQw4w9WgXcQ' in url:
            url_key = 'Rick Roll (dQw4w9WgXcQ)'
        elif 'jNQXAC9IVRw' in url:
            url_key = 'Me at the zoo (jNQXAC9IVRw)'
        elif '9bZkp7q19f0' in url:
            url_key = 'Gangnam Style (9bZkp7q19f0)'
        else:
            url_key = url[:50] + '...' if len(url) > 50 else url
        
        url_stats[url_key]['total'] += 1
        if result['success']:
            url_stats[url_key]['success'] += 1
    
    # Calculate average times
    for client, stats in client_stats.items():
        if stats['times']:
            stats['avg_time'] = sum(stats['times']) / len(stats['times'])
    
    # Generate report
    report = []
    report.append("=" * 80)
    report.append("YT-DLP CONFIGURATION TEST RESULTS ANALYSIS")
    report.append("=" * 80)
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("SUMMARY:")
    report.append(f"  Total Tests Run: {total_tests}")
    report.append(f"  Successful Tests: {success_count}")
    report.append(f"  Failed Tests: {len(failed_tests)}")
    report.append(f"  Overall Success Rate: {success_rate:.1f}%")
    report.append("")
    
    # Player client analysis
    report.append("PLAYER CLIENT CONFIGURATION ANALYSIS:")
    report.append("-" * 50)
    report.append(f"{'Client Configuration':<30} {'Success Rate':<15} {'Avg Time (s)':<15}")
    report.append("-" * 50)
    
    for client, stats in sorted(client_stats.items(), 
                               key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0,
                               reverse=True):
        success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        avg_time = stats['avg_time'] if stats['avg_time'] > 0 else 0
        client_short = client[:28] + '..' if len(client) > 30 else client
        report.append(f"{client_short:<30} {success_rate:>6.1f}% ({stats['success']}/{stats['total']}){avg_time:>12.2f}")
    
    report.append("")
    
    # User agent analysis
    report.append("USER AGENT ANALYSIS:")
    report.append("-" * 40)
    for ua, stats in sorted(user_agent_stats.items(), 
                           key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0,
                           reverse=True):
        success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        report.append(f"{ua}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
    
    report.append("")
    
    # URL analysis
    report.append("TEST URL ANALYSIS:")
    report.append("-" * 40)
    for url, stats in sorted(url_stats.items(), 
                            key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0,
                            reverse=True):
        success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        report.append(f"{url}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
    
    report.append("")
    
    # Top performing configurations
    if successful_tests:
        report.append("TOP 5 FASTEST SUCCESSFUL CONFIGURATIONS:")
        report.append("-" * 50)
        fastest_tests = sorted([t for t in successful_tests if t.get('download_time')], 
                              key=lambda x: x['download_time'])[:5]
        
        for i, test in enumerate(fastest_tests, 1):
            report.append(f"{i}. {test['test_name']}")
            report.append(f"   Time: {test['download_time']:.2f}s")
            report.append(f"   Clients: {test.get('player_clients', 'Unknown')}")
            report.append(f"   Size: {test.get('file_size', 0) / 1024 / 1024:.1f} MB")
            report.append("")
    
    # Failed tests analysis
    if failed_tests:
        report.append("FAILED TESTS ANALYSIS:")
        report.append("-" * 40)
        error_counts = defaultdict(int)
        for test in failed_tests:
            error = test.get('error', 'Unknown error')
            error_counts[error] += 1
        
        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            report.append(f"{count}x: {error}")
        report.append("")
    
    # Recommendations
    report.append("RECOMMENDATIONS:")
    report.append("-" * 40)
    
    # Find best client configuration
    best_client = max(client_stats.items(), 
                     key=lambda x: (x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0, -x[1]['avg_time']))
    
    if best_client[1]['total'] > 0:
        best_rate = (best_client[1]['success'] / best_client[1]['total']) * 100
        report.append(f"1. BEST PLAYER CLIENT: {best_client[0]}")
        report.append(f"   Success Rate: {best_rate:.1f}%")
        report.append(f"   Average Download Time: {best_client[1]['avg_time']:.2f}s")
        report.append("")
    
    # Find best user agent
    best_ua = max(user_agent_stats.items(), 
                 key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0)
    
    if best_ua[1]['total'] > 0:
        best_ua_rate = (best_ua[1]['success'] / best_ua[1]['total']) * 100
        report.append(f"2. BEST USER AGENT: {best_ua[0]}")
        report.append(f"   Success Rate: {best_ua_rate:.1f}%")
        report.append("")
    
    if success_rate == 100:
        report.append("3. RESULT: ALL CONFIGURATIONS TESTED WORK PERFECTLY!")
        report.append("   Any of the tested player client combinations should work reliably.")
        report.append("   Consider using the fastest configuration for best performance.")
    elif success_rate >= 90:
        report.append("3. RESULT: EXCELLENT RELIABILITY")
        report.append("   Most configurations work well. Stick with top-performing clients.")
    elif success_rate >= 70:
        report.append("3. RESULT: GOOD RELIABILITY") 
        report.append("   Most configurations work. Avoid failed configurations.")
    else:
        report.append("3. RESULT: MIXED RESULTS")
        report.append("   Use only the successful configurations identified above.")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)

def main():
    """Main function to run the analysis."""
    log_file = "ytdlp_config_tests.log"
    
    try:
        print("Parsing test results...")
        results = parse_log_file(log_file)
        
        print("Analyzing results...")
        report = analyze_results(results)
        
        print(report)
        
        # Save report to file
        report_file = f"ytdlp_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\nDetailed report saved to: {report_file}")
        
    except FileNotFoundError:
        print(f"Error: Log file '{log_file}' not found.")
    except Exception as e:
        print(f"Error analyzing results: {str(e)}")

if __name__ == "__main__":
    main()
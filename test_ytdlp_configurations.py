#!/usr/bin/env python3
"""
Comprehensive yt-dlp Configuration Tester

This script systematically tests different yt-dlp configuration options
to find the most reliable settings for YouTube downloads.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import yt_dlp
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ytdlp_config_tests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class YTDLPConfigTester:
    """Test different yt-dlp configurations systematically."""
    
    def __init__(self, test_output_dir: str = "test_downloads"):
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(exist_ok=True)
        self.results = []
        
        # Test URLs - using publicly available videos
        self.test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - classic test video
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # "Me at the zoo" - first YouTube video
            "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY - Gangnam Style
        ]
        
        # Different player client configurations to test
        self.player_client_configs = [
            {
                "name": "original_android_creator",
                "clients": ['android_creator', 'web', 'android', 'ios'],
                "description": "Original configuration from codebase"
            },
            {
                "name": "tv_web_safari_web",
                "clients": ['tv', 'web_safari', 'web'],
                "description": "TV and web safari clients"
            },
            {
                "name": "mweb_web",
                "clients": ['mweb', 'web'],
                "description": "Mobile web and web clients"
            },
            {
                "name": "web_only",
                "clients": ['web'],
                "description": "Web client only"
            },
            {
                "name": "android_only",
                "clients": ['android'],
                "description": "Android client only"
            },
            {
                "name": "tv_only",
                "clients": ['tv'],
                "description": "TV client only"
            },
            {
                "name": "ios_only",
                "clients": ['ios'],
                "description": "iOS client only"
            },
            {
                "name": "android_creator_only",
                "clients": ['android_creator'],
                "description": "Android creator client only"
            },
            {
                "name": "mweb_only",
                "clients": ['mweb'],
                "description": "Mobile web client only"
            },
            {
                "name": "web_safari_only",
                "clients": ['web_safari'],
                "description": "Web Safari client only"
            }
        ]
        
        # Different user agents to test
        self.user_agents = [
            {
                "name": "default",
                "agent": None,
                "description": "Default yt-dlp user agent"
            },
            {
                "name": "chrome_windows",
                "agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "description": "Chrome on Windows"
            },
            {
                "name": "firefox_windows",
                "agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
                "description": "Firefox on Windows"
            },
            {
                "name": "safari_mac",
                "agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
                "description": "Safari on macOS"
            },
            {
                "name": "mobile_android",
                "agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
                "description": "Chrome mobile on Android"
            }
        ]
        
        # Timeout and retry configurations
        self.timeout_configs = [
            {"name": "default", "socket_timeout": None, "fragment_retries": None},
            {"name": "short_timeout", "socket_timeout": 10, "fragment_retries": 3},
            {"name": "medium_timeout", "socket_timeout": 30, "fragment_retries": 5},
            {"name": "long_timeout", "socket_timeout": 60, "fragment_retries": 10},
        ]

    def create_base_config(self, test_dir: Path) -> Dict:
        """Create base yt-dlp configuration."""
        return {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',  # Lower quality for faster tests
            'outtmpl': str(test_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            'writeinfojson': True,  # Save metadata for analysis
            'extract_flat': False,
            'ignoreerrors': False,
            'no_color': True,
        }

    def test_configuration(self, 
                         url: str,
                         player_clients: List[str],
                         user_agent: Optional[str] = None,
                         with_cookies: bool = False,
                         timeout_config: Dict = None,
                         test_name: str = "test") -> Dict:
        """Test a specific yt-dlp configuration."""
        
        test_dir = self.test_output_dir / f"{test_name}_{int(time.time())}"
        test_dir.mkdir(exist_ok=True)
        
        # Create configuration
        config = self.create_base_config(test_dir)
        
        # Add player clients
        if player_clients:
            config['player_client'] = player_clients
        
        # Add user agent
        if user_agent:
            config['http_headers'] = {'User-Agent': user_agent}
        
        # Add timeout settings
        if timeout_config:
            if timeout_config.get('socket_timeout'):
                config['socket_timeout'] = timeout_config['socket_timeout']
            if timeout_config.get('fragment_retries'):
                config['fragment_retries'] = timeout_config['fragment_retries']
        
        # Add cookies if requested
        if with_cookies:
            # Note: In a real scenario, you'd specify actual cookie file
            config['cookiefile'] = 'cookies.txt'  # This will fail if file doesn't exist
        
        result = {
            'test_name': test_name,
            'url': url,
            'player_clients': player_clients,
            'user_agent': user_agent,
            'with_cookies': with_cookies,
            'timeout_config': timeout_config,
            'config': config,
            'success': False,
            'error_message': None,
            'warning_messages': [],
            'download_time': None,
            'video_info': None,
            'file_size': None,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Testing configuration: {test_name}")
        logger.info(f"  URL: {url}")
        logger.info(f"  Player clients: {player_clients}")
        logger.info(f"  User agent: {user_agent[:50] + '...' if user_agent else 'Default'}")
        logger.info(f"  With cookies: {with_cookies}")
        
        start_time = time.time()
        
        try:
            with yt_dlp.YoutubeDL(config) as ydl:
                # First, try to extract info without downloading
                try:
                    info = ydl.extract_info(url, download=False)
                    result['video_info'] = {
                        'title': info.get('title'),
                        'duration': info.get('duration'),
                        'uploader': info.get('uploader'),
                        'view_count': info.get('view_count'),
                        'upload_date': info.get('upload_date')
                    }
                    logger.info(f"  Successfully extracted info: {info.get('title')}")
                except Exception as e:
                    result['error_message'] = f"Info extraction failed: {str(e)}"
                    logger.error(f"  Info extraction failed: {str(e)}")
                    return result
                
                # Now try to download
                try:
                    ydl.download([url])
                    
                    # Check if download was successful
                    downloaded_files = list(test_dir.glob("*"))
                    video_files = [f for f in downloaded_files if f.suffix in ['.mp4', '.webm', '.mkv']]
                    
                    if video_files:
                        result['success'] = True
                        result['file_size'] = video_files[0].stat().st_size
                        logger.info(f"  SUCCESS - Downloaded: {video_files[0].name} ({result['file_size']} bytes)")
                    else:
                        result['error_message'] = "Download completed but no video file found"
                        logger.warning(f"  Download completed but no video file found")
                        
                except Exception as e:
                    result['error_message'] = f"Download failed: {str(e)}"
                    logger.error(f"  Download failed: {str(e)}")
                    
        except Exception as e:
            result['error_message'] = f"Configuration error: {str(e)}"
            logger.error(f"  Configuration error: {str(e)}")
        
        result['download_time'] = time.time() - start_time
        logger.info(f"  Test completed in {result['download_time']:.2f} seconds")
        
        # Clean up test files to save space
        try:
            for file in test_dir.glob("*"):
                file.unlink()
            test_dir.rmdir()
        except Exception as e:
            logger.warning(f"  Cleanup failed: {str(e)}")
        
        return result

    def run_comprehensive_tests(self) -> List[Dict]:
        """Run comprehensive tests with all configuration combinations."""
        logger.info("Starting comprehensive yt-dlp configuration tests")
        
        test_count = 0
        total_tests = (
            len(self.test_urls) * 
            len(self.player_client_configs) * 
            len(self.user_agents) * 
            len(self.timeout_configs) * 
            2  # with and without cookies
        )
        
        logger.info(f"Total tests to run: {total_tests}")
        
        for url_idx, url in enumerate(self.test_urls):
            logger.info(f"\n=== Testing URL {url_idx + 1}/{len(self.test_urls)}: {url} ===")
            
            for client_config in self.player_client_configs:
                for ua_config in self.user_agents:
                    for timeout_config in self.timeout_configs:
                        for with_cookies in [False, True]:
                            test_count += 1
                            
                            test_name = (
                                f"url{url_idx + 1}_"
                                f"{client_config['name']}_"
                                f"{ua_config['name']}_"
                                f"{timeout_config['name']}_"
                                f"{'cookies' if with_cookies else 'nocookies'}"
                            )
                            
                            logger.info(f"\n--- Test {test_count}/{total_tests}: {test_name} ---")
                            
                            result = self.test_configuration(
                                url=url,
                                player_clients=client_config['clients'],
                                user_agent=ua_config['agent'],
                                with_cookies=with_cookies,
                                timeout_config=timeout_config,
                                test_name=test_name
                            )
                            
                            self.results.append(result)
                            
                            # Save intermediate results
                            if test_count % 10 == 0:
                                self.save_results()
                            
                            # Brief pause between tests
                            time.sleep(1)
        
        logger.info("\nAll tests completed!")
        return self.results

    def run_focused_tests(self) -> List[Dict]:
        """Run focused tests with most promising configurations only."""
        logger.info("Starting focused yt-dlp configuration tests")
        
        # Focus on most promising configurations
        focused_client_configs = [
            {"name": "web_only", "clients": ['web']},
            {"name": "tv_only", "clients": ['tv']},
            {"name": "android_only", "clients": ['android']},
            {"name": "mweb_web", "clients": ['mweb', 'web']},
        ]
        
        focused_user_agents = [
            {"name": "default", "agent": None},
            {"name": "chrome_windows", "agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"},
        ]
        
        focused_timeout_configs = [
            {"name": "default", "socket_timeout": None, "fragment_retries": None},
            {"name": "medium_timeout", "socket_timeout": 30, "fragment_retries": 5},
        ]
        
        test_count = 0
        for url_idx, url in enumerate(self.test_urls):
            logger.info(f"\n=== Testing URL {url_idx + 1}/{len(self.test_urls)}: {url} ===")
            
            for client_config in focused_client_configs:
                for ua_config in focused_user_agents:
                    for timeout_config in focused_timeout_configs:
                        test_count += 1
                        
                        test_name = (
                            f"focused_url{url_idx + 1}_"
                            f"{client_config['name']}_"
                            f"{ua_config['name']}_"
                            f"{timeout_config['name']}"
                        )
                        
                        logger.info(f"\n--- Focused Test {test_count}: {test_name} ---")
                        
                        result = self.test_configuration(
                            url=url,
                            player_clients=client_config['clients'],
                            user_agent=ua_config['agent'],
                            with_cookies=False,
                            timeout_config=timeout_config,
                            test_name=test_name
                        )
                        
                        self.results.append(result)
                        
                        # Brief pause between tests
                        time.sleep(1)
        
        logger.info("\nFocused tests completed!")
        return self.results

    def save_results(self, filename: str = None):
        """Save test results to JSON file."""
        if not filename:
            filename = f"ytdlp_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filename}")

    def generate_report(self) -> str:
        """Generate a detailed test report."""
        if not self.results:
            return "No test results available."
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        report = []
        report.append("=" * 80)
        report.append("YT-DLP CONFIGURATION TEST REPORT")
        report.append("=" * 80)
        report.append(f"Total Tests: {total_tests}")
        report.append(f"Successful: {successful_tests}")
        report.append(f"Failed: {total_tests - successful_tests}")
        report.append(f"Success Rate: {success_rate:.1f}%")
        report.append("")
        
        # Group results by configuration type
        client_success = {}
        ua_success = {}
        timeout_success = {}
        
        for result in self.results:
            # Track client success
            client_key = str(result['player_clients'])
            if client_key not in client_success:
                client_success[client_key] = {'total': 0, 'success': 0}
            client_success[client_key]['total'] += 1
            if result['success']:
                client_success[client_key]['success'] += 1
            
            # Track user agent success
            ua_key = result['user_agent'][:50] + "..." if result['user_agent'] else "Default"
            if ua_key not in ua_success:
                ua_success[ua_key] = {'total': 0, 'success': 0}
            ua_success[ua_key]['total'] += 1
            if result['success']:
                ua_success[ua_key]['success'] += 1
        
        # Player client analysis
        report.append("PLAYER CLIENT ANALYSIS:")
        report.append("-" * 40)
        for client, stats in sorted(client_success.items(), 
                                  key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0, 
                                  reverse=True):
            success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
            report.append(f"{client}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        report.append("")
        
        # User agent analysis
        report.append("USER AGENT ANALYSIS:")
        report.append("-" * 40)
        for ua, stats in sorted(ua_success.items(), 
                               key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0, 
                               reverse=True):
            success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
            report.append(f"{ua}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        report.append("")
        
        # Failed tests analysis
        failed_tests = [r for r in self.results if not r['success']]
        if failed_tests:
            report.append("FAILED TESTS ANALYSIS:")
            report.append("-" * 40)
            error_counts = {}
            for result in failed_tests:
                error = result['error_message'] or "Unknown error"
                error_counts[error] = error_counts.get(error, 0) + 1
            
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                report.append(f"{count}x: {error}")
            report.append("")
        
        # Successful configurations
        successful_tests = [r for r in self.results if r['success']]
        if successful_tests:
            report.append("TOP SUCCESSFUL CONFIGURATIONS:")
            report.append("-" * 40)
            # Group by configuration and show success rate
            config_groups = {}
            for result in successful_tests[:10]:  # Show top 10
                config_key = f"{result['player_clients']} + {result['user_agent'][:30] + '...' if result['user_agent'] else 'Default'}"
                if config_key not in config_groups:
                    config_groups[config_key] = []
                config_groups[config_key].append(result)
            
            for config, results in list(config_groups.items())[:5]:  # Top 5 configs
                avg_time = sum(r['download_time'] for r in results if r['download_time']) / len(results)
                report.append(f"Config: {config}")
                report.append(f"  Success count: {len(results)}")
                report.append(f"  Avg download time: {avg_time:.2f}s")
                report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Main function to run the tests."""
    print("YT-DLP Configuration Tester")
    print("=" * 50)
    
    tester = YTDLPConfigTester()
    
    # Run focused tests by default (faster and more practical)
    print("Running focused tests (most promising configurations)...")
    
    try:
        tester.run_focused_tests()
        
        # Save results and generate report
        tester.save_results()
        
        report = tester.generate_report()
        print("\n" + report)
        
        # Save report to file
        report_filename = f"ytdlp_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\nDetailed report saved to: {report_filename}")
        print(f"Raw results saved to: ytdlp_test_results_*.json")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        if tester.results:
            tester.save_results()
            print("Partial results saved.")
    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
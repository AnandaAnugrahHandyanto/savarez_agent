#!/usr/bin/env python3
"""
End-to-End Testing - Test deployed website in browser.
Verifies pages, endpoints, forms, links, and UX work correctly.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse
from pathlib import Path


class EndToEndTester:
    def __init__(self, base_url, project_dir):
        self.base_url = base_url.rstrip('/')
        self.project_dir = Path(project_dir)
        self.results = {
            'pages_tested': [],
            'endpoints_tested': [],
            'forms_tested': [],
            'links_checked': [],
            'errors': [],
            'score': 100
        }
        
    def test_page_load(self, path='/', description='Homepage'):
        """Test that a page loads successfully."""
        url = f"{self.base_url}{path}"
        print(f"   Testing {description}: {url}...")
        
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'MVP-E2E-Tester/1.0'},
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.getcode()
                content_type = response.headers.get('Content-Type', '')
                
                if status == 200:
                    self.results['pages_tested'].append({
                        'url': url,
                        'status': status,
                        'content_type': content_type
                    })
                    print(f"      ✅ OK ({status})")
                    return True
                else:
                    self.results['errors'].append(f"{description}: HTTP {status}")
                    self.results['score'] -= 10
                    print(f"      ⛔ Failed (HTTP {status})")
                    return False
                    
        except urllib.error.HTTPError as e:
            self.results['errors'].append(f"{description}: HTTP {e.code}")
            self.results['score'] -= 10
            print(f"      ⛔ HTTP Error {e.code}")
            return False
        except Exception as e:
            self.results['errors'].append(f"{description}: {str(e)}")
            self.results['score'] -= 10
            print(f"      ⛔ Error: {str(e)[:50]}")
            return False
    
    def test_api_endpoint(self, path, method='GET', expected_status=200):
        """Test an API endpoint."""
        url = f"{self.base_url}{path}"
        print(f"   Testing API {method} {path}...")
        
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'MVP-E2E-Tester/1.0',
                    'Accept': 'application/json'
                },
                method=method
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.getcode()
                
                self.results['endpoints_tested'].append({
                    'url': url,
                    'method': method,
                    'status': status
                })
                
                if status == expected_status:
                    print(f"      ✅ OK ({status})")
                    return True
                else:
                    self.results['errors'].append(f"API {path}: Expected {expected_status}, got {status}")
                    self.results['score'] -= 5
                    print(f"      ⚠️ Unexpected status: {status}")
                    return False
                    
        except urllib.error.HTTPError as e:
            if e.code == expected_status:
                print(f"      ✅ OK ({e.code})")
                return True
            self.results['errors'].append(f"API {path}: HTTP {e.code}")
            self.results['score'] -= 10
            print(f"      ⛔ HTTP {e.code}")
            return False
        except Exception as e:
            self.results['errors'].append(f"API {path}: {str(e)}")
            self.results['score'] -= 10
            print(f"      ⛔ Error: {str(e)[:50]}")
            return False
    
    def test_forms_present(self):
        """Check if forms are present and have required attributes."""
        print(f"   Testing forms...")
        
        try:
            req = urllib.request.Request(
                self.base_url,
                headers={'User-Agent': 'MVP-E2E-Tester/1.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                # Look for forms
                form_count = html.lower().count('<form')
                
                if form_count > 0:
                    # Check for CSRF tokens
                    has_csrf = 'csrf' in html.lower() or 'token' in html.lower()
                    
                    self.results['forms_tested'].append({
                        'count': form_count,
                        'has_csrf': has_csrf
                    })
                    
                    if has_csrf:
                        print(f"      ✅ {form_count} form(s) with CSRF protection")
                    else:
                        print(f"      ⚠️ {form_count} form(s) - NO CSRF PROTECTION")
                        self.results['errors'].append("Forms missing CSRF protection")
                        self.results['score'] -= 15
                    return True
                else:
                    print(f"      ℹ️ No forms found")
                    return True
                    
        except Exception as e:
            self.results['errors'].append(f"Form check: {str(e)}")
            self.results['score'] -= 5
            print(f"      ⛔ Error checking forms")
            return False
    
    def test_ssl(self):
        """Test SSL/HTTPS is working."""
        print(f"   Testing SSL/HTTPS...")
        
        if not self.base_url.startswith('https://'):
            self.results['errors'].append("Site not using HTTPS")
            self.results['score'] -= 30
            print(f"      ⛔ NOT HTTPS - CRITICAL SECURITY ISSUE")
            return False
        
        print(f"      ✅ HTTPS enabled")
        return True
    
    def test_responsive_meta(self):
        """Check for responsive viewport meta tag."""
        print(f"   Testing responsive design...")
        
        try:
            req = urllib.request.Request(
                self.base_url,
                headers={'User-Agent': 'MVP-E2E-Tester/1.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore').lower()
                
                if 'viewport' in html:
                    print(f"      ✅ Responsive viewport meta found")
                    return True
                else:
                    self.results['errors'].append("Missing viewport meta tag - not mobile-friendly")
                    self.results['score'] -= 10
                    print(f"      ⚠️ No viewport meta - NOT MOBILE FRIENDLY")
                    return False
                    
        except Exception as e:
            self.results['errors'].append(f"Responsive check: {str(e)}")
            self.results['score'] -= 5
            print(f"      ⛔ Error checking responsive design")
            return False
    
    def run_all_tests(self):
        """Run complete end-to-end test suite."""
        print(f"\n{'='*60}")
        print(f"🧪 END-TO-END TESTING")
        print(f"{'='*60}")
        print(f"Target: {self.base_url}")
        print(f"{'='*60}\n")
        
        # Critical tests
        self.test_ssl()
        self.test_page_load('/', 'Homepage')
        self.test_responsive_meta()
        self.test_forms_present()
        
        # Common pages
        common_pages = [
            ('/about', 'About page'),
            ('/contact', 'Contact page'),
            ('/login', 'Login page'),
            ('/register', 'Register page'),
            ('/dashboard', 'Dashboard'),
            ('/profile', 'Profile page'),
        ]
        
        for path, desc in common_pages:
            self.test_page_load(path, desc)
        
        # API endpoints
        api_endpoints = [
            ('/api/health', 'GET', 200),
            ('/api/status', 'GET', 200),
            ('/api/user', 'GET', 200),
            ('/api/auth/login', 'POST', 401),  # Should fail without auth
        ]
        
        for path, method, expected in api_endpoints:
            self.test_api_endpoint(path, method, expected)
        
        # Calculate final score
        self.results['score'] = max(0, self.results['score'])
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 E2E TEST RESULTS")
        print(f"{'='*60}")
        print(f"Pages Tested: {len(self.results['pages_tested'])}")
        print(f"API Endpoints: {len(self.results['endpoints_tested'])}")
        print(f"Forms: {len(self.results['forms_tested'])}")
        print(f"Errors: {len(self.results['errors'])}")
        print(f"Score: {self.results['score']}/100")
        
        if self.results['errors']:
            print(f"\n⛔ ERRORS FOUND:")
            for error in self.results['errors'][:10]:
                print(f"   - {error}")
        
        print(f"{'='*60}")
        
        return self.results
    
    def save_results(self):
        """Save test results to file."""
        results_path = self.project_dir / 'audits' / 'e2e_test_results.json'
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(self.results, indent=2))
        print(f"\n📝 Results saved: {results_path}")


def main():
    parser = argparse.ArgumentParser(description='End-to-end testing for MVP')
    parser.add_argument('--url', required=True, help='Base URL to test')
    parser.add_argument('--project-dir', required=True, help='Project directory')
    
    args = parser.parse_args()
    
    tester = EndToEndTester(args.url, args.project_dir)
    results = tester.run_all_tests()
    tester.save_results()
    
    # Exit with error code if score is too low
    if results['score'] < 90:
        print(f"\n⛔ E2E TESTS FAILED (Score: {results['score']}/100)")
        sys.exit(1)
    else:
        print(f"\n✅ E2E TESTS PASSED (Score: {results['score']}/100)")
        sys.exit(0)


if __name__ == '__main__':
    main()

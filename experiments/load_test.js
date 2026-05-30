import http from 'k6/http';
import { check, group, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp-up: 10 users
    { duration: '1m', target: 50 },   // Ramp-up: 50 users
    { duration: '2m', target: 50 },   // Stay at 50 users
    { duration: '30s', target: 0 },   // Ramp-down: 0 users
  ],
};

export default function () {
  group('Paginação Offset V1', function () {
    const res = http.get(`${BASE_URL}/v1/produtos?limit=50&offset=0`);
    check(res, {
      'status is 200': (r) => r.status === 200,
      'has data': (r) => r.json('data') !== undefined,
      'pagination strategy is offset': (r) => r.json('pagination.strategy') === 'offset',
    });
  });

  sleep(0.5);

  group('Paginação Cursor V1', function () {
    const res = http.get(`${BASE_URL}/v1/produtos/cursor?limit=50&cursor=0`);
    check(res, {
      'status is 200': (r) => r.status === 200,
      'has data': (r) => r.json('data') !== undefined,
      'pagination strategy is cursor': (r) => r.json('pagination.strategy') === 'cursor',
    });
  });

  sleep(0.5);

  group('Paginação Offset V2', function () {
    const res = http.get(`${BASE_URL}/v2/produtos?limit=50&offset=0`);
    check(res, {
      'status is 200': (r) => r.status === 200,
      'has meta': (r) => r.json('meta') !== undefined,
      'version is v2': (r) => r.json('version') === 'v2',
    });
  });

  sleep(0.5);

  group('Versionamento via Headers', function () {
    const res = http.get(`${BASE_URL}/produtos?limit=50&offset=0`, {
      headers: {
        'Accept': 'application/vnd.api.v2+json',
      },
    });
    check(res, {
      'status is 200': (r) => r.status === 200,
      'version is v2': (r) => r.json('version') === 'v2',
    });
  });

  sleep(1);
}

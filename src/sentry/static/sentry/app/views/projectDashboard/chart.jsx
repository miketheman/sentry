import PropTypes from 'prop-types';
import React from 'react';
import createReactClass from 'create-react-class';
import moment from 'moment';
import ApiMixin from '../../mixins/apiMixin';
import BarChart from '../../components/barChart';
import DynamicWrapper from '../../components/dynamicWrapper';
import LoadingError from '../../components/loadingError';
import LoadingIndicator from '../../components/loadingIndicator';
import ProjectState from '../../mixins/projectState';

const ProjectChart = createReactClass({
  displayName: 'ProjectChart',

  propTypes: {
    dateSince: PropTypes.number.isRequired,
    resolution: PropTypes.string.isRequired,
    environment: PropTypes.object,
  },

  mixins: [ApiMixin, ProjectState],

  getInitialState() {
    return {
      loading: true,
      error: false,
      stats: [],
      releaseList: [],
    };
  },

  componentWillMount() {
    this.fetchData();
  },

  componentWillReceiveProps() {
    this.setState(
      {
        loading: true,
        error: false,
      },
      this.fetchData
    );
  },

  getStatsEndpoint() {
    let org = this.getOrganization();
    let project = this.getProject();
    return '/projects/' + org.slug + '/' + project.slug + '/stats/';
  },

  getProjectReleasesEndpoint() {
    let org = this.getOrganization();
    let project = this.getProject();
    return '/projects/' + org.slug + '/' + project.slug + '/releases/';
  },

  fetchData() {
    const statsQuery = {
      since: this.props.dateSince,
      resolution: this.props.resolution,
      stat: 'generated',
    };

    const releasesQuery = {};

    if (this.props.environment) {
      statsQuery.environment = this.props.environment.name;
      releasesQuery.environment = this.props.environment.name;
    }

    this.api.request(this.getStatsEndpoint(), {
      query: statsQuery,
      success: data => {
        this.setState({
          stats: data,
          error: false,
          loading: false,
        });
      },
      error: () => {
        this.setState({
          error: true,
          loading: false,
        });
      },
    });

    this.api.request(this.getProjectReleasesEndpoint(), {
      query: releasesQuery,
      success: (data, _, jqXHR) => {
        this.setState({
          releaseList: data,
        });
      },
    });
  },

  renderChart() {
    let points = this.state.stats.map(point => {
      return {x: point[0], y: point[1]};
    });
    let startX = this.props.dateSince;
    let markers = this.state.releaseList
      .filter(release => {
        let date = new Date(release.dateCreated).getTime() / 1000;
        return date >= startX;
      })
      .map(release => {
        return {
          label: 'Version ' + release.shortVersion,
          x: new Date(release.dateCreated).getTime() / 1000,
        };
      });

    return (
      <div className="chart-wrapper">
        <BarChart
          points={points}
          markers={markers}
          label="events"
          height={150}
          className="standard-barchart"
        />
        <small className="date-legend">
          <DynamicWrapper
            fixed="Test Date 1, 2000"
            value={moment(this.props.dateSince * 1000).format('LL')}
          />
        </small>
      </div>
    );
  },

  render() {
    return this.state.loading ? (
      <LoadingIndicator />
    ) : this.state.error ? (
      <LoadingError onRetry={this.fetchData} />
    ) : (
      this.renderChart()
    );
  },
});

export default ProjectChart;

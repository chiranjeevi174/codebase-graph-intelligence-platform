/**
 * Application State Manager - Centralized reactive state container.
 */

class AppState {
  constructor() {
    this.selectedRepository = "sample_repo";
    this.selectedBranch = "main";
    this.selectedCommit = "HEAD";

    this.healthStatus = null;
    this.repositories = [];

    this.activeTab = "query"; // 'query' | 'impact' | 'api-flow' | 'diff'

    this.currentQueryResponse = null;
    this.currentGraphData = null;
    this.currentImpactResult = null;
    this.currentApiFlowResult = null;
    this.currentDiffResult = null;

    this.selectedNode = null;
    this.selectedSource = null;

    this.listeners = new Set();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify(event, data) {
    for (const listener of this.listeners) {
      listener(event, data, this);
    }
  }

  setRepository(repoId) {
    this.selectedRepository = repoId;
    this.notify("repo_changed", repoId);
  }

  setTab(tabName) {
    this.activeTab = tabName;
    this.notify("tab_changed", tabName);
  }

  setHealth(health) {
    this.healthStatus = health;
    this.notify("health_updated", health);
  }

  setRepositories(repos) {
    this.repositories = repos;
    this.notify("repositories_updated", repos);
  }

  setQueryResponse(response) {
    this.currentQueryResponse = response;
    this.notify("query_response_updated", response);
  }

  setGraphData(graphData) {
    this.currentGraphData = graphData;
    this.notify("graph_data_updated", graphData);
  }

  setImpactResult(impact) {
    this.currentImpactResult = impact;
    this.notify("impact_updated", impact);
  }

  setApiFlowResult(apiFlow) {
    this.currentApiFlowResult = apiFlow;
    this.notify("api_flow_updated", apiFlow);
  }

  setDiffResult(diff) {
    this.currentDiffResult = diff;
    this.notify("diff_updated", diff);
  }

  setSelectedNode(node) {
    this.selectedNode = node;
    this.notify("node_selected", node);
  }

  setSelectedSource(source) {
    this.selectedSource = source;
    this.notify("source_selected", source);
  }
}

export const state = new AppState();

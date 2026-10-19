import {createApp} from 'vue';
import App from './App.vue';
import AdminDashboard from './components/AdminDashboard.vue';
import './style.css';
createApp(window.location.pathname==='/admin'?AdminDashboard:App).mount('#app');
